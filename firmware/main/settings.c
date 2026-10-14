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
#define SETTINGS_VERSION 1

static const char *TAG = "settings";
static SemaphoreHandle_t s_lock;
static settings_t s_settings;

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
    strcpy(s->ap_password, SETTINGS_DEFAULT_AP_PASSWORD);
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
    size_t pw = strnlen(s->ap_password, sizeof(s->ap_password));
    if (pw < 8 || pw > 63) {
        return "Wi-Fi password must be 8-63 characters";
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
    ESP_LOGI(TAG, "home %s, radii %u/%u m, %u presses, %u s arrival", s_settings.home_set ? "set" : "not set",
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
    xSemaphoreGive(s_lock);
    return err;
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
