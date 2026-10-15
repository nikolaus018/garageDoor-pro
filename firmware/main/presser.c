#include "presser.h"

#include "board.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "presser";

typedef struct {
    uint16_t count;     // presses; 0 = stop
    uint16_t hold_ms;   // > 0: hold the switch closed instead
} cmd_t;

static QueueHandle_t s_queue;
static volatile uint16_t s_remaining;
static volatile bool s_holding;

static void press_once(void)
{
    gpio_set_level(PIN_SWITCH, 1);
    vTaskDelay(pdMS_TO_TICKS(PRESS_PULSE_MS));
    gpio_set_level(PIN_SWITCH, 0);
}

static void hold(uint16_t ms)
{
    ESP_LOGI(TAG, "holding for %u ms", ms);
    s_holding = true;
    gpio_set_level(PIN_SWITCH, 1);
    cmd_t next;
    xQueuePeek(s_queue, &next, pdMS_TO_TICKS(ms));   // a new command ends the hold early
    gpio_set_level(PIN_SWITCH, 0);
    s_holding = false;
}

static void presser_task(void *arg)
{
    TickType_t next = xTaskGetTickCount();
    for (;;) {
        TickType_t wait = portMAX_DELAY;
        if (s_remaining > 0) {
            TickType_t now = xTaskGetTickCount();
            wait = (int32_t)(next - now) > 0 ? next - now : 0;
        }
        cmd_t cmd;
        if (xQueueReceive(s_queue, &cmd, wait) == pdTRUE) {
            s_remaining = cmd.hold_ms ? 0 : cmd.count;
            if (cmd.hold_ms) {
                hold(cmd.hold_ms);
            } else if (cmd.count) {
                ESP_LOGI(TAG, "pressing %u times", cmd.count);
            } else {
                ESP_LOGI(TAG, "stop");
            }
            next = xTaskGetTickCount();
            continue;
        }
        press_once();
        s_remaining--;
        next += pdMS_TO_TICKS(PRESS_PERIOD_MS);
    }
}

void presser_init(void)
{
    // Idle level before enabling the output so the switch never closes during boot
    // (R9 on the PCB, R2 on the perfboard, holds it low until here).
    gpio_set_level(PIN_SWITCH, 0);
    gpio_config_t io = { .pin_bit_mask = 1ULL << PIN_SWITCH, .mode = GPIO_MODE_OUTPUT };
    ESP_ERROR_CHECK(gpio_config(&io));
    s_queue = xQueueCreate(4, sizeof(cmd_t));
    xTaskCreate(presser_task, "presser", 3072, NULL, 10, NULL);
}

void presser_press(uint16_t count)
{
    cmd_t cmd = { .count = count };
    xQueueSend(s_queue, &cmd, portMAX_DELAY);
}

void presser_press_for(uint16_t seconds)
{
    presser_press((uint16_t)((seconds * 1000u + PRESS_PERIOD_MS - 1) / PRESS_PERIOD_MS));
}

void presser_hold(uint16_t ms)
{
    cmd_t cmd = { .hold_ms = ms };
    xQueueSend(s_queue, &cmd, portMAX_DELAY);
}

void presser_stop(void)
{
    presser_press(0);
}

uint16_t presser_remaining(void)
{
    return s_remaining;
}

bool presser_holding(void)
{
    return s_holding;
}
