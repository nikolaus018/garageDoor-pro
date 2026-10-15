// garageDoor-pro: opens the garage when the car leaves home and when it arrives (GPS).
#include "app.h"

#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "gnss.h"
#include "presser.h"
#include "ui.h"
#include "web.h"

#define FIX_FRESH_S 5
#define MARK_VALID_AFTER_S 60   // a new OTA image that runs this long is kept (else rolled back)

static const char *TAG = "app";
static SemaphoreHandle_t s_lock;
static trip_t s_trip;
static trip_fix_t s_fix;
static bool s_have_fix;

static void apply(unsigned actions, trip_parked_t parked)
{
    if (actions & TRIP_ACT_SAVE_PARKED) {
        settings_set_parked(parked);
    }
    if (actions & TRIP_ACT_STOP_PRESSING) {
        presser_stop();
    }
    settings_t s = settings_get();
    if ((actions & TRIP_ACT_PRESS_LEAVE) && s.leave_presses) {
        presser_press(s.leave_presses);
    }
    if (actions & TRIP_ACT_PRESS_ARRIVE) {
        presser_press_for(s.arrive_duration_s);
    }
}

static void update_ui(void)
{
    trip_config_t cfg = settings_trip_config();
    xSemaphoreTake(s_lock, portMAX_DELAY);
    bool usable = s_have_fix && trip_fix_usable(&s_fix);
    xSemaphoreGive(s_lock);
    if (!cfg.home_set) {
        ui_set_status(UI_NO_HOME);
    } else if (usable && gnss_seconds_since_message() < FIX_FRESH_S) {
        ui_set_status(UI_FIX);
    } else {
        ui_set_status(UI_NO_FIX);
    }
}

static void on_fix(const trip_fix_t *fix)
{
    trip_config_t cfg = settings_trip_config();
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_fix = *fix;
    s_have_fix = true;
    trip_state_t before = s_trip.state;
    unsigned actions = trip_on_fix(&s_trip, &cfg, fix);
    trip_state_t after = s_trip.state;
    trip_parked_t parked = s_trip.parked;
    double d = s_trip.distance_m;
    xSemaphoreGive(s_lock);
    if (before != after) {
        ESP_LOGI(TAG, "%s -> %s (%.0f m from home)", trip_state_name(before), trip_state_name(after), d);
    }
    apply(actions, parked);
}

void app_get_status(app_status_t *out)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    out->state = s_trip.state;
    out->parked = s_trip.parked;
    out->distance_m = s_trip.distance_m;
    out->have_fix = s_have_fix;
    out->fix = s_fix;
    out->fix_usable = s_have_fix && trip_fix_usable(&s_fix);
    xSemaphoreGive(s_lock);
    out->gnss_age_s = gnss_seconds_since_message();
    out->presses_remaining = presser_remaining();
    out->holding = presser_holding();
    out->uptime_s = (uint32_t)(esp_timer_get_time() / 1000000);
}

const char *app_set_home(int32_t lat_e7, int32_t lon_e7)
{
    settings_t s = settings_get();
    s.home_set = true;
    s.home_lat_e7 = lat_e7;
    s.home_lon_e7 = lon_e7;
    const char *err = settings_validate(&s);
    if (err) {
        return err;
    }
    if (settings_set(&s) != ESP_OK) {
        return "Could not save settings";
    }
    trip_config_t cfg = settings_trip_config();
    xSemaphoreTake(s_lock, portMAX_DELAY);
    unsigned actions = trip_on_home_set(&s_trip, &cfg);
    trip_parked_t parked = s_trip.parked;
    xSemaphoreGive(s_lock);
    apply(actions, parked);
    ESP_LOGI(TAG, "home set to %.6f, %.6f", lat_e7 * 1e-7, lon_e7 * 1e-7);
    update_ui();
    return NULL;
}

const char *app_set_home_here(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    bool ok = s_have_fix && trip_fix_usable(&s_fix) && gnss_seconds_since_message() < FIX_FRESH_S;
    trip_fix_t f = s_fix;
    xSemaphoreGive(s_lock);
    if (!ok) {
        return "No accurate GPS fix right now. Move the antenna so it sees the sky and wait for the fix.";
    }
    return app_set_home(f.lat_e7, f.lon_e7);
}

const char *app_apply_settings(const settings_t *in)
{
    settings_t s = settings_get();
    s.arrive_radius_m = in->arrive_radius_m;
    s.leave_radius_m = in->leave_radius_m;
    s.leave_presses = in->leave_presses;
    s.arrive_duration_s = in->arrive_duration_s;
    const char *err = settings_validate(&s);
    if (err) {
        return err;
    }
    return settings_set(&s) == ESP_OK ? NULL : "Could not save settings";
}

void app_test_press(void)
{
    presser_press(1);
}

void app_test_hold(void)
{
    presser_hold(HOLD_TEST_MS);
}

// Button callbacks run in the small UI task; the main loop does the actual work.
static volatile bool s_req_setup, s_req_reset;

static void on_setup(void)
{
    s_req_setup = true;
}

static void on_factory_reset(void)
{
    s_req_reset = true;
}

void app_main(void)
{
    presser_init();   // first: switch output defined low as early as possible
    s_lock = xSemaphoreCreateMutex();
    ESP_ERROR_CHECK(settings_init());

    trip_config_t cfg = settings_trip_config();
    unsigned actions = trip_start(&s_trip, &cfg, settings_get_parked());
    ESP_LOGI(TAG, "start: %s", trip_state_name(s_trip.state));
    apply(actions, s_trip.parked);

    ui_callbacks_t cb = { .on_setup = on_setup, .on_factory_reset = on_factory_reset };
    ui_start(&cb);
    web_init();
    if (!cfg.home_set) {
        web_start();  // brand-new board: open the setup Wi-Fi right away
    }
    gnss_start(on_fix);

    bool marked = false;
    for (;;) {
        if (s_req_reset) {
            ESP_LOGW(TAG, "factory reset");
            presser_stop();
            settings_factory_reset();
            esp_restart();
        }
        if (s_req_setup) {
            s_req_setup = false;
            web_start();
        }
        update_ui();
        if (!marked && esp_timer_get_time() > MARK_VALID_AFTER_S * 1000000LL) {
            // Reached only if the image boots and runs normally; otherwise the bootloader rolls back.
            esp_ota_mark_app_valid_cancel_rollback();
            marked = true;
        }
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}
