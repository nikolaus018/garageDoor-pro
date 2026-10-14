#include "gnss.h"

#include <string.h>

#include "board.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ubx.h"

#define DEFAULT_BAUD 9600
#define RUN_BAUD 115200
#define RECONFIGURE_AFTER_S 10   // no NAV-PVT for this long: send the configuration again
#define RESET_AFTER_S 30         // ... still nothing: hardware reset of the receiver

static const char *TAG = "gnss";
static gnss_fix_cb_t s_cb;
static volatile int64_t s_last_msg_us = -1;

static void send_config(void)
{
    // RAM layer only: the receiver loses it on power-off and gets it again on every boot.
    static const ubx_cfg_item_t items[] = {
        { UBX_CFG_UART1_BAUDRATE, RUN_BAUD },
        { UBX_CFG_UART1INPROT_UBX, 1 },
        { UBX_CFG_UART1OUTPROT_UBX, 1 },
        { UBX_CFG_UART1OUTPROT_NMEA, 0 },
        { UBX_CFG_MSGOUT_UBX_NAV_PVT_UART1, 1 },
        { UBX_CFG_RATE_MEAS, 1000 },
        { UBX_CFG_NAVSPG_DYNMODEL, UBX_DYNMODEL_AUTOMOTIVE },
    };
    uint8_t frame[96];
    size_t n = ubx_build_valset(frame, sizeof frame, UBX_LAYER_RAM, items, sizeof items / sizeof items[0]);
    // The receiver may be at its default 9600 (power-on) or already at 115200 (only the ESP32
    // restarted), so send at both rates and then listen at 115200.
    const int rates[] = { DEFAULT_BAUD, RUN_BAUD };
    for (int i = 0; i < 2; i++) {
        uart_set_baudrate(GNSS_UART, rates[i]);
        uart_write_bytes(GNSS_UART, frame, n);
        uart_wait_tx_done(GNSS_UART, pdMS_TO_TICKS(200));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    uart_set_baudrate(GNSS_UART, RUN_BAUD);
    uart_flush_input(GNSS_UART);
}

static void hardware_reset(void)
{
    ESP_LOGW(TAG, "receiver silent, resetting it");
    gpio_set_level(PIN_GPS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(PIN_GPS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));
}

uint32_t gnss_seconds_since_message(void)
{
    int64_t last = s_last_msg_us;
    return last < 0 ? UINT32_MAX : (uint32_t)((esp_timer_get_time() - last) / 1000000);
}

static void gnss_task(void *arg)
{
    static ubx_parser_t parser;
    ubx_parser_reset(&parser);
    uint8_t buf[128];
    int64_t silent_since = esp_timer_get_time();
    int64_t last_config = silent_since;
    bool reset_done = false;

    send_config();
    for (;;) {
        int n = uart_read_bytes(GNSS_UART, buf, sizeof buf, pdMS_TO_TICKS(200));
        for (int i = 0; i < n; i++) {
            if (!ubx_parser_feed(&parser, buf[i]) || parser.cls != UBX_CLASS_NAV || parser.id != UBX_ID_NAV_PVT) {
                continue;
            }
            ubx_nav_pvt_t pvt;
            if (!ubx_decode_nav_pvt(parser.payload, parser.len, &pvt)) {
                continue;
            }
            s_last_msg_us = silent_since = esp_timer_get_time();
            reset_done = false;
            trip_fix_t fix = { .valid = pvt.fix_ok && pvt.fix_type >= 2 && pvt.fix_type <= 4,
                               .lat_e7 = pvt.lat_e7, .lon_e7 = pvt.lon_e7, .h_acc_mm = pvt.h_acc_mm,
                               .num_sv = pvt.num_sv };
            s_cb(&fix);
        }
        int64_t now = esp_timer_get_time();
        int64_t silent_s = (now - silent_since) / 1000000;
        if (silent_s >= RESET_AFTER_S && !reset_done) {
            hardware_reset();
            send_config();
            reset_done = true;
            silent_since = last_config = esp_timer_get_time();
        } else if (silent_s >= RECONFIGURE_AFTER_S && now - last_config >= RECONFIGURE_AFTER_S * 1000000LL) {
            ESP_LOGW(TAG, "no NAV-PVT for %llds, reconfiguring", (long long)silent_s);
            send_config();
            last_config = esp_timer_get_time();
        }
    }
}

void gnss_start(gnss_fix_cb_t cb)
{
    s_cb = cb;
    gpio_set_level(PIN_GPS_RESET_N, 1);
    gpio_config_t rst = { .pin_bit_mask = 1ULL << PIN_GPS_RESET_N, .mode = GPIO_MODE_OUTPUT_OD };
    ESP_ERROR_CHECK(gpio_config(&rst));

    uart_config_t cfg = {
        .baud_rate = DEFAULT_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(GNSS_UART, 2048, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(GNSS_UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(GNSS_UART, PIN_GPS_TX_TO_GNSS, PIN_GPS_RX_FROM_GNSS, UART_PIN_NO_CHANGE,
                                 UART_PIN_NO_CHANGE));
    xTaskCreate(gnss_task, "gnss", 6144, NULL, 8, NULL);
}
