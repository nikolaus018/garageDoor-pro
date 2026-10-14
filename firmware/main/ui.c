#include "ui.h"

#include "board.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define TICK_MS 50
#define SETUP_HOLD_MS 3000
#define RESET_HOLD_MS 10000
#define PATTERN_PERIOD_MS 3000
#define FLASH_ON_MS 60
#define FLASH_GAP_MS 250

static ui_callbacks_t s_cb;
static volatile ui_status_t s_status = UI_NO_FIX;
static volatile bool s_setup;

void ui_set_status(ui_status_t s)
{
    s_status = s;
}

void ui_set_setup_mode(bool on)
{
    s_setup = on;
}

static bool pattern_led(uint32_t t_ms, int flashes)
{
    uint32_t t = t_ms % PATTERN_PERIOD_MS;
    for (int i = 0; i < flashes; i++) {
        uint32_t start = i * (FLASH_ON_MS + FLASH_GAP_MS);
        if (t >= start && t < start + FLASH_ON_MS) {
            return true;
        }
    }
    return false;
}

static void ui_task(void *arg)
{
    uint32_t t = 0, held = 0;
    for (;;) {
        bool pressed = gpio_get_level(PIN_BUTTON) == 0;
        if (pressed) {
            held += TICK_MS;
        } else if (held) {
            if (held >= RESET_HOLD_MS) {
                s_cb.on_factory_reset();
            } else if (held >= SETUP_HOLD_MS) {
                s_cb.on_setup();
            }
            held = 0;
        }

        bool led;
        if (held >= RESET_HOLD_MS) {
            led = (t / 50) % 2;            // rapid flicker: release now for factory reset
        } else if (held >= SETUP_HOLD_MS) {
            led = true;                    // solid: release now for setup
        } else if (s_setup) {
            led = (t / 125) % 2;           // 4 Hz
        } else {
            led = pattern_led(t, s_status == UI_FIX ? 1 : s_status == UI_NO_FIX ? 2 : 3);
        }
        gpio_set_level(PIN_LED_STATUS, led ^ LED_ACTIVE_LOW);

        vTaskDelay(pdMS_TO_TICKS(TICK_MS));
        t += TICK_MS;
    }
}

void ui_start(const ui_callbacks_t *cb)
{
    s_cb = *cb;
    gpio_set_level(PIN_LED_STATUS, LED_ACTIVE_LOW);  // off
    gpio_config_t led = { .pin_bit_mask = 1ULL << PIN_LED_STATUS, .mode = GPIO_MODE_OUTPUT };
    ESP_ERROR_CHECK(gpio_config(&led));
    gpio_config_t btn = { .pin_bit_mask = 1ULL << PIN_BUTTON, .mode = GPIO_MODE_INPUT,
                          .pull_up_en = GPIO_PULLUP_ENABLE };
    ESP_ERROR_CHECK(gpio_config(&btn));
    xTaskCreate(ui_task, "ui", 2560, NULL, 5, NULL);
}
