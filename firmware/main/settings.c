#include "settings.h"

#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "nvs.h"
#include "nvs_flash.h"

#define NS "garage"
#define KEY_SETTINGS "cfg"
#define KEY_PARKED "parked"
#define KEY_BOOTS "boots"
#define KEY_LOG "log"
#define LOG_VERSION 1
#define SETTINGS_VERSION 2   // 2: Wi-Fi password fields removed (the setup Wi-Fi is open)

static const char *TAG = "settings";
static SemaphoreHandle_t s_lock;
static settings_t s_settings;
static uint16_t s_boot;

typedef struct {
    uint8_t version, head, count, reserved;
    settings_log_entry_t e[SETTINGS_LOG_LEN];
} stored_log_t;
static stored_log_t s_log;

typedef struct {
    uint32_t version;
    settings_t s;
} stored_t;

static void defaults(settings_t *s)
{
    memset(s, 0, sizeof(*s));
    s->arrive_radius_m = 150;
    s->leave_radius_m = 300;
    s->leave_presses = 10;
    s->arrive_duration_s = 180;
}

const char *settings_validate(const settings_t *s)
{
    if (s->arrive_radius_m < 30 || s->arrive_radius_m > 2000) {
        return "Arrive radius must be 30-2000 m";
    }
    if (s->leave_radius_m < s->arrive_radius_m + 50 || s->leave_radius_m > 5000) {
        return "Leave radius must be at least 50 m larger than the arrive radius (max 5000 m)";
    }
    if (s->leave_presses > 30) {
        return "Presses on leaving must be 0-30";
    }
    if (s->arrive_duration_s < 10 || s->arrive_duration_s > 600) {
        return "Arrival pressing must last 10-600 s";
    }
    if (s->home_set && (s->home_lat_e7 < -900000000 || s->home_lat_e7 > 900000000 ||
                        s->home_lon_e7 < -1800000000 || s->home_lon_e7 > 1800000000)) {
        return "Home coordinates out of range";
    }
    return NULL;
}

static esp_err_t store(const settings_t *s)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    stored_t st = { .version = SETTINGS_VERSION, .s = *s };
    err = nvs_set_blob(h, KEY_SETTINGS, &st, sizeof(st));
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

esp_err_t settings_init(void)
{
    s_lock = xSemaphoreCreateMutex();
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS format changed, erasing");
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        return err;
    }
    defaults(&s_settings);
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) == ESP_OK) {
        stored_t st;
        size_t len = sizeof(st);
        if (nvs_get_blob(h, KEY_SETTINGS, &st, &len) == ESP_OK && len == sizeof(st) &&
            st.version == SETTINGS_VERSION && settings_validate(&st.s) == NULL) {
            s_settings = st.s;
        }
        nvs_close(h);
    }
    if (nvs_open(NS, NVS_READWRITE, &h) == ESP_OK) {
        uint16_t boots = 0;
        nvs_get_u16(h, KEY_BOOTS, &boots);
        s_boot = boots + 1;
        if (s_boot == 0) {
            s_boot = 1;   // wrapped
        }
        size_t len = sizeof(s_log);
        if (nvs_get_blob(h, KEY_LOG, &s_log, &len) != ESP_OK || len != sizeof(s_log) ||
            s_log.version != LOG_VERSION || s_log.head >= SETTINGS_LOG_LEN || s_log.count > SETTINGS_LOG_LEN) {
            memset(&s_log, 0, sizeof(s_log));
            s_log.version = LOG_VERSION;
        }
        if (nvs_set_u16(h, KEY_BOOTS, s_boot) == ESP_OK) {
            nvs_commit(h);
        }
        nvs_close(h);
    }
    ESP_LOGI(TAG, "boot %u, home %s, radii %u/%u m, %u presses, %u s arrival", s_boot, s_settings.home_set ? "set" : "not set",
             s_settings.arrive_radius_m, s_settings.leave_radius_m, s_settings.leave_presses,
             s_settings.arrive_duration_s);
    return ESP_OK;
}

settings_t settings_get(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    settings_t s = s_settings;
    xSemaphoreGive(s_lock);
    return s;
}

esp_err_t settings_set(const settings_t *s)
{
    if (settings_validate(s)) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    esp_err_t err = store(s);
    if (err == ESP_OK) {
        s_settings = *s;
    }
    xSemaphoreGive(s_lock);
    return err;
}

esp_err_t settings_factory_reset(void)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err == ESP_OK) {
        err = nvs_erase_all(h);
        if (err == ESP_OK) {
            err = nvs_commit(h);
        }
        nvs_close(h);
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    defaults(&s_settings);
    memset(&s_log, 0, sizeof(s_log));
    s_log.version = LOG_VERSION;
    xSemaphoreGive(s_lock);
    return err;
}

uint16_t settings_boot_count(void)
{
    return s_boot;
}

void settings_log_add(const settings_log_entry_t *e)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_log.e[s_log.head] = *e;
    s_log.head = (s_log.head + 1) % SETTINGS_LOG_LEN;
    if (s_log.count < SETTINGS_LOG_LEN) {
        s_log.count++;
    }
    stored_log_t copy = s_log;
    xSemaphoreGive(s_lock);
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err == ESP_OK) {
        err = nvs_set_blob(h, KEY_LOG, &copy, sizeof(copy));
        if (err == ESP_OK) {
            err = nvs_commit(h);
        }
        nvs_close(h);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "saving the event log failed: %s", esp_err_to_name(err));
    }
}

size_t settings_log_get(settings_log_entry_t *out, size_t max)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    size_t n = s_log.count < max ? s_log.count : max;
    size_t first = (s_log.head + SETTINGS_LOG_LEN - s_log.count) % SETTINGS_LOG_LEN;
    first = (first + (s_log.count - n)) % SETTINGS_LOG_LEN;   // the newest n if max is smaller
    for (size_t i = 0; i < n; i++) {
        out[i] = s_log.e[(first + i) % SETTINGS_LOG_LEN];
    }
    xSemaphoreGive(s_lock);
    return n;
}

trip_parked_t settings_get_parked(void)
{
    uint8_t v = PARKED_HOME;
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, KEY_PARKED, &v);
        nvs_close(h);
    }
    return v == PARKED_AWAY ? PARKED_AWAY : PARKED_HOME;
}

esp_err_t settings_set_parked(trip_parked_t p)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_u8(h, KEY_PARKED, (uint8_t)p);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "saving parked state failed: %s", esp_err_to_name(err));
    }
    return err;
}

trip_config_t settings_trip_config(void)
{
    settings_t s = settings_get();
    trip_config_t c = { .home_set = s.home_set, .home_lat_e7 = s.home_lat_e7, .home_lon_e7 = s.home_lon_e7,
                        .arrive_radius_m = s.arrive_radius_m, .leave_radius_m = s.leave_radius_m };
    return c;
}
