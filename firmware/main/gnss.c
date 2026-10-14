#include "gnss.h"

#include <string.h>

#include "board.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nmea.h"
#include "ubx.h"

// Works with u-blox M9/M10 (configured to UBX NAV-PVT, 115200 baud) and, as a fallback, with any
// module that outputs NMEA GGA (NEO-6M, ATGM336H, other u-blox generations, ...) at a common rate.
#define RUN_BAUD 115200
#define LISTEN_MS 2500           // per baud rate while searching (GGA comes once per second)
#define RESTART_AFTER_S 10       // nothing usable for this long: search again
#define UBX_PREFERRED_S 3        // ignore NMEA while NAV-PVT arrived recently

static const char *TAG = "gnss";
static const int BAUDS[] = { 115200, 9600, 38400, 57600, 230400 };

static gnss_fix_cb_t s_cb;
static volatile int64_t s_last_msg_us = -1;
static volatile int64_t s_last_ubx_us = -1;
static volatile gnss_protocol_t s_protocol = GNSS_NONE;
static volatile int s_baud;

static ubx_parser_t s_ubx;
static nmea_parser_t s_nmea;

static void configure_ubx(void)
{
    // RAM layer only: applied again on every boot. Receivers that don't know CFG-VALSET (older
    // u-blox, other brands) ignore it and keep sending NMEA, which we handle as well.
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
    for (size_t i = 0; i < sizeof BAUDS / sizeof BAUDS[0]; i++) {
        uart_set_baudrate(GNSS_UART, BAUDS[i]);
        uart_write_bytes(GNSS_UART, frame, n);
        uart_wait_tx_done(GNSS_UART, pdMS_TO_TICKS(200));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static void hardware_reset(void)
{
#if HAS_GPS_RESET
    ESP_LOGW(TAG, "receiver silent, resetting it");
    gpio_set_level(PIN_GPS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(PIN_GPS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));
#endif
}

// Feeds received bytes to both parsers; reports fixes. Returns true if anything valid arrived.
static bool process(const uint8_t *buf, int n)
{
    bool got = false;
    for (int i = 0; i < n; i++) {
        if (ubx_parser_feed(&s_ubx, buf[i]) && s_ubx.cls == UBX_CLASS_NAV && s_ubx.id == UBX_ID_NAV_PVT) {
            ubx_nav_pvt_t pvt;
            if (ubx_decode_nav_pvt(s_ubx.payload, s_ubx.len, &pvt)) {
                s_last_msg_us = s_last_ubx_us = esp_timer_get_time();
                s_protocol = GNSS_UBX;
                got = true;
                trip_fix_t fix = { .valid = pvt.fix_ok && pvt.fix_type >= 2 && pvt.fix_type <= 4,
                                   .lat_e7 = pvt.lat_e7, .lon_e7 = pvt.lon_e7, .h_acc_mm = pvt.h_acc_mm,
                                   .num_sv = pvt.num_sv };
                s_cb(&fix);
            }
        }
        nmea_gga_t gga;
        if (nmea_feed(&s_nmea, (char)buf[i], &gga)) {
            int64_t now = esp_timer_get_time();
            got = true;
            s_last_msg_us = now;
            if (s_last_ubx_us >= 0 && now - s_last_ubx_us < UBX_PREFERRED_S * 1000000LL) {
                continue;
            }
            s_protocol = GNSS_NMEA;
            trip_fix_t fix = { .valid = gga.fix, .lat_e7 = gga.lat_e7, .lon_e7 = gga.lon_e7,
                               .h_acc_mm = gga.h_acc_mm, .num_sv = gga.num_sv };
            s_cb(&fix);
        }
    }
    return got;
}

static bool listen(int baud, int ms)
{
    uart_set_baudrate(GNSS_UART, baud);
    uart_flush_input(GNSS_UART);
    ubx_parser_reset(&s_ubx);
    nmea_parser_reset(&s_nmea);
    uint8_t buf[128];
    int64_t end = esp_timer_get_time() + ms * 1000LL;
    while (esp_timer_get_time() < end) {
        int n = uart_read_bytes(GNSS_UART, buf, sizeof buf, pdMS_TO_TICKS(100));
        if (n > 0 && process(buf, n)) {
            return true;
        }
    }
    return false;
}

// Configures u-blox receivers, then finds the baud rate the receiver actually talks at.
static void connect(void)
{
    configure_ubx();
    for (;;) {
        for (size_t i = 0; i < sizeof BAUDS / sizeof BAUDS[0]; i++) {
            if (listen(BAUDS[i], LISTEN_MS)) {
                s_baud = BAUDS[i];
                ESP_LOGI(TAG, "receiver found at %d baud (%s)", s_baud, s_protocol == GNSS_UBX ? "UBX" : "NMEA");
                return;
            }
        }
        ESP_LOGW(TAG, "no GPS data at any baud rate, check wiring (module TX -> GPIO%d)", PIN_GPS_RX_FROM_GNSS);
        hardware_reset();
        configure_ubx();
    }
}

uint32_t gnss_seconds_since_message(void)
{
    int64_t last = s_last_msg_us;
    return last < 0 ? UINT32_MAX : (uint32_t)((esp_timer_get_time() - last) / 1000000);
}

gnss_protocol_t gnss_protocol(void)
{
    return s_protocol;
}

static void gnss_task(void *arg)
{
    uint8_t buf[128];
    connect();
    for (;;) {
        int n = uart_read_bytes(GNSS_UART, buf, sizeof buf, pdMS_TO_TICKS(200));
        if (n > 0) {
            process(buf, n);
        }
        uint32_t silent = gnss_seconds_since_message();
        if (silent >= RESTART_AFTER_S) {
            // connect() returns only once data flows again; a full fruitless scan resets the receiver.
            ESP_LOGW(TAG, "no GPS data for %lus, searching again", (unsigned long)silent);
            connect();
        }
    }
}

void gnss_start(gnss_fix_cb_t cb)
{
    s_cb = cb;
#if HAS_GPS_RESET
    gpio_set_level(PIN_GPS_RESET_N, 1);
    gpio_config_t rst = { .pin_bit_mask = 1ULL << PIN_GPS_RESET_N, .mode = GPIO_MODE_OUTPUT_OD };
    ESP_ERROR_CHECK(gpio_config(&rst));
#endif
    uart_config_t cfg = {
        .baud_rate = RUN_BAUD,
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
