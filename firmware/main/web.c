#include "web.h"

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_netif.h"   // before dns_server.h, which uses its types
#include "dns_server.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "settings.h"
#include "ui.h"

#define BODY_MAX 512
#define AP_IP "192.168.4.1"

static const char *TAG = "web";
extern const uint8_t index_html_start[] asm("_binary_index_html_start");
extern const uint8_t index_html_end[] asm("_binary_index_html_end");

static SemaphoreHandle_t s_lock;
static esp_netif_t *s_netif;
static httpd_handle_t s_http;
static dns_server_handle_t s_dns;
static esp_timer_handle_t s_idle_timer, s_restart_timer, s_reboot_timer;
static volatile int64_t s_last_activity_us;
static bool s_active;

static void touch(void)
{
    s_last_activity_us = esp_timer_get_time();
}

// ---------- helpers ----------

static void url_decode(char *s)
{
    char *o = s;
    for (char *p = s; *p; p++) {
        if (*p == '+') {
            *o++ = ' ';
        } else if (*p == '%' && isxdigit((unsigned char)p[1]) && isxdigit((unsigned char)p[2])) {
            char hex[3] = { p[1], p[2], 0 };
            *o++ = (char)strtol(hex, NULL, 16);
            p += 2;
        } else {
            *o++ = *p;
        }
    }
    *o = 0;
}

static bool form_value(const char *body, const char *key, char *out, size_t len)
{
    if (httpd_query_key_value(body, key, out, len) != ESP_OK) {
        return false;
    }
    url_decode(out);
    return true;
}

static bool form_long(const char *body, const char *key, long min, long max, long *out)
{
    char v[24];
    if (!form_value(body, key, v, sizeof v)) {
        return false;
    }
    char *end;
    long n = strtol(v, &end, 10);
    if (end == v || *end || n < min || n > max) {
        return false;
    }
    *out = n;
    return true;
}

static esp_err_t read_body(httpd_req_t *req, char *buf, size_t len)
{
    if (req->content_len >= len) {
        return ESP_FAIL;
    }
    size_t got = 0;
    while (got < req->content_len) {
        int r = httpd_req_recv(req, buf + got, req->content_len - got);
        if (r <= 0) {
            return ESP_FAIL;
        }
        got += r;
    }
    buf[got] = 0;
    return ESP_OK;
}

static esp_err_t send_json(httpd_req_t *req, const char *status, const char *json)
{
    httpd_resp_set_status(req, status);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_sendstr(req, json);
}

static esp_err_t send_result(httpd_req_t *req, const char *err)
{
    if (!err) {
        return send_json(req, "200 OK", "{\"ok\":true}");
    }
    char json[256];
    snprintf(json, sizeof json, "{\"ok\":false,\"error\":\"%s\"}", err);  // messages contain no quotes
    return send_json(req, "400 Bad Request", json);
}

// Everything except status and changing the password needs the default password changed first.
static bool locked(httpd_req_t *req)
{
    if (settings_get().password_changed) {
        return false;
    }
    send_json(req, "403 Forbidden",
              "{\"ok\":false,\"error\":\"Change the Wi-Fi password first.\"}");
    return true;
}

// ---------- handlers ----------

static esp_err_t index_get(httpd_req_t *req)
{
    touch();
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_send(req, (const char *)index_html_start, index_html_end - index_html_start);
}

static esp_err_t status_get(httpd_req_t *req)
{
    touch();
    app_status_t st;
    app_get_status(&st);
    settings_t s = settings_get();
    const esp_app_desc_t *app = esp_app_get_description();
    char json[768];
    snprintf(json, sizeof json,
             "{\"state\":\"%s\",\"parked\":\"%s\",\"distance_m\":%.0f,"
             "\"gps\":{\"seen\":%s,\"usable\":%s,\"fix\":%s,\"lat\":%.7f,\"lon\":%.7f,\"acc_m\":%.1f,\"sats\":%u,"
             "\"age_s\":%ld},"
             "\"home\":{\"set\":%s,\"lat\":%.7f,\"lon\":%.7f},"
             "\"settings\":{\"arrive_radius_m\":%u,\"leave_radius_m\":%u,\"leave_presses\":%u,"
             "\"arrive_duration_s\":%u},"
             "\"presses_remaining\":%u,\"password_changed\":%s,\"version\":\"%s\",\"uptime_s\":%lu}",
             trip_state_name(st.state), st.parked == PARKED_HOME ? "HOME" : "AWAY", st.distance_m,
             st.have_fix ? "true" : "false", st.fix_usable ? "true" : "false", st.fix.valid ? "true" : "false",
             st.fix.lat_e7 * 1e-7, st.fix.lon_e7 * 1e-7, st.fix.h_acc_mm / 1000.0, st.fix.num_sv,
             st.gnss_age_s == UINT32_MAX ? -1L : (long)st.gnss_age_s,
             s.home_set ? "true" : "false", s.home_lat_e7 * 1e-7, s.home_lon_e7 * 1e-7,
             s.arrive_radius_m, s.leave_radius_m, s.leave_presses, s.arrive_duration_s,
             st.presses_remaining, s.password_changed ? "true" : "false", app->version,
             (unsigned long)st.uptime_s);
    return send_json(req, "200 OK", json);
}

static esp_err_t home_post(httpd_req_t *req)
{
    touch();
    if (locked(req)) {
        return ESP_OK;
    }
    char body[BODY_MAX], mode[16], lat[24], lon[24];
    if (read_body(req, body, sizeof body) != ESP_OK) {
        return send_result(req, "Bad request");
    }
    if (form_value(body, "mode", mode, sizeof mode) && strcmp(mode, "here") == 0) {
        return send_result(req, app_set_home_here());
    }
    if (!form_value(body, "lat", lat, sizeof lat) || !form_value(body, "lon", lon, sizeof lon)) {
        return send_result(req, "Enter latitude and longitude");
    }
    char *e1, *e2;
    double la = strtod(lat, &e1), lo = strtod(lon, &e2);
    if (e1 == lat || *e1 || e2 == lon || *e2 || fabs(la) > 90 || fabs(lo) > 180) {
        return send_result(req, "Latitude/longitude must be decimal degrees, e.g. 48.208176 and 16.373819");
    }
    return send_result(req, app_set_home((int32_t)lround(la * 1e7), (int32_t)lround(lo * 1e7)));
}

static esp_err_t settings_post(httpd_req_t *req)
{
    touch();
    if (locked(req)) {
        return ESP_OK;
    }
    char body[BODY_MAX];
    long arrive, leave, presses, duration;
    if (read_body(req, body, sizeof body) != ESP_OK ||
        !form_long(body, "arrive_radius_m", 0, 65535, &arrive) ||
        !form_long(body, "leave_radius_m", 0, 65535, &leave) ||
        !form_long(body, "leave_presses", 0, 255, &presses) ||
        !form_long(body, "arrive_duration_s", 0, 65535, &duration)) {
        return send_result(req, "All settings must be whole numbers");
    }
    settings_t s = { .arrive_radius_m = arrive, .leave_radius_m = leave, .leave_presses = presses,
                     .arrive_duration_s = duration };
    return send_result(req, app_apply_settings(&s));
}

static esp_err_t test_post(httpd_req_t *req)
{
    touch();
    if (locked(req)) {
        return ESP_OK;
    }
    app_test_press();
    return send_result(req, NULL);
}

static void apply_ap_config(void);

static void restart_ap_cb(void *arg)
{
    if (s_active) {
        apply_ap_config();  // new password; clients reconnect with it
    }
}

static esp_err_t password_post(httpd_req_t *req)
{
    touch();
    char body[BODY_MAX], pw[96];
    if (read_body(req, body, sizeof body) != ESP_OK || !form_value(body, "password", pw, sizeof pw)) {
        return send_result(req, "Enter a password");
    }
    settings_t s = settings_get();
    if (strlen(pw) >= sizeof s.ap_password) {
        return send_result(req, "Wi-Fi password must be 8-63 characters");
    }
    if (strcmp(pw, SETTINGS_DEFAULT_AP_PASSWORD) == 0) {
        return send_result(req, "Choose a password other than the default");
    }
    strcpy(s.ap_password, pw);
    s.password_changed = true;
    const char *err = settings_validate(&s);
    if (!err && settings_set(&s) != ESP_OK) {
        err = "Could not save settings";
    }
    esp_err_t r = send_result(req, err);
    if (!err) {
        esp_timer_start_once(s_restart_timer, 1500 * 1000);  // let the response reach the phone first
    }
    return r;
}

static void reboot_cb(void *arg)
{
    esp_restart();
}

static esp_err_t ota_post(httpd_req_t *req)
{
    touch();
    if (locked(req)) {
        return ESP_OK;
    }
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    if (!part || req->content_len == 0 || req->content_len > part->size) {
        return send_result(req, "Firmware file missing or too large");
    }
    esp_ota_handle_t ota;
    if (esp_ota_begin(part, OTA_SIZE_UNKNOWN, &ota) != ESP_OK) {
        return send_result(req, "Could not start the update");
    }
    char buf[1024];
    size_t left = req->content_len;
    while (left > 0) {
        int r = httpd_req_recv(req, buf, left < sizeof buf ? left : sizeof buf);
        if (r == HTTPD_SOCK_ERR_TIMEOUT) {
            continue;
        }
        if (r <= 0 || esp_ota_write(ota, buf, r) != ESP_OK) {
            esp_ota_abort(ota);
            return send_result(req, "Upload failed");
        }
        left -= r;
        touch();
    }
    // esp_ota_end verifies the image (magic, chip, checksum); a broken file is rejected here.
    if (esp_ota_end(ota) != ESP_OK || esp_ota_set_boot_partition(part) != ESP_OK) {
        return send_result(req, "Not a valid garageDoor-pro firmware image");
    }
    ESP_LOGI(TAG, "update written to %s, restarting", part->label);
    esp_timer_start_once(s_reboot_timer, 1500 * 1000);
    return send_result(req, NULL);
}

static esp_err_t not_found(httpd_req_t *req, httpd_err_code_t err)
{
    // Captive portal: send every unknown URL (phone connectivity checks) to the panel.
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://" AP_IP "/");
    return httpd_resp_send(req, "Redirect to the garageDoor panel", HTTPD_RESP_USE_STRLEN);
}

// ---------- Wi-Fi / servers ----------

static void apply_ap_config(void)
{
    settings_t s = settings_get();
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
    wifi_config_t cfg = { 0 };
    int n = snprintf((char *)cfg.ap.ssid, sizeof cfg.ap.ssid, "GarageDoor-%02X%02X", mac[4], mac[5]);
    cfg.ap.ssid_len = n;
    strlcpy((char *)cfg.ap.password, s.ap_password, sizeof cfg.ap.password);
    cfg.ap.channel = 6;
    cfg.ap.max_connection = 2;
    cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
    cfg.ap.pmf_cfg.required = false;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &cfg));
    ESP_LOGI(TAG, "setup Wi-Fi \"%s\" on http://" AP_IP, (char *)cfg.ap.ssid);
}

static void stop_task(void *arg)
{
    web_stop();
    vTaskDelete(NULL);
}

static void idle_cb(void *arg)
{
    // Runs in the esp_timer task, which must not block: stop the servers from a short task.
    if (s_active && esp_timer_get_time() - s_last_activity_us > WEB_IDLE_TIMEOUT_S * 1000000LL) {
        ESP_LOGI(TAG, "no activity for %d s, turning setup Wi-Fi off", WEB_IDLE_TIMEOUT_S);
        xTaskCreate(stop_task, "web_stop", 3072, NULL, 5, NULL);
    }
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WIFI_EVENT_AP_STACONNECTED) {
        touch();
    }
}

void web_init(void)
{
    s_lock = xSemaphoreCreateMutex();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_netif = esp_netif_create_default_wifi_ap();
    wifi_init_config_t wcfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wcfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_AP_STACONNECTED, wifi_event, NULL));

    const esp_timer_create_args_t idle = { .callback = idle_cb, .name = "web_idle" };
    const esp_timer_create_args_t restart = { .callback = restart_ap_cb, .name = "web_ap" };
    const esp_timer_create_args_t reboot = { .callback = reboot_cb, .name = "web_reboot" };
    ESP_ERROR_CHECK(esp_timer_create(&idle, &s_idle_timer));
    ESP_ERROR_CHECK(esp_timer_create(&restart, &s_restart_timer));
    ESP_ERROR_CHECK(esp_timer_create(&reboot, &s_reboot_timer));
}

void web_start(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_active) {
        touch();
        xSemaphoreGive(s_lock);
        return;
    }
    touch();
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    apply_ap_config();
    ESP_ERROR_CHECK(esp_wifi_start());

    // DHCP option 114 (RFC 8910) points phones straight at the panel.
    static const char uri[] = "http://" AP_IP;
    esp_netif_dhcps_stop(s_netif);
    esp_netif_dhcps_option(s_netif, ESP_NETIF_OP_SET, ESP_NETIF_CAPTIVEPORTAL_URI, (void *)uri, strlen(uri));
    esp_netif_dhcps_start(s_netif);

    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.max_uri_handlers = 12;
    cfg.max_open_sockets = 7;
    cfg.lru_purge_enable = true;
    cfg.recv_wait_timeout = 15;
    cfg.stack_size = 8192;
    if (httpd_start(&s_http, &cfg) == ESP_OK) {
        static const httpd_uri_t uris[] = {
            { .uri = "/", .method = HTTP_GET, .handler = index_get },
            { .uri = "/api/status", .method = HTTP_GET, .handler = status_get },
            { .uri = "/api/home", .method = HTTP_POST, .handler = home_post },
            { .uri = "/api/settings", .method = HTTP_POST, .handler = settings_post },
            { .uri = "/api/test", .method = HTTP_POST, .handler = test_post },
            { .uri = "/api/password", .method = HTTP_POST, .handler = password_post },
            { .uri = "/api/ota", .method = HTTP_POST, .handler = ota_post },
        };
        for (size_t i = 0; i < sizeof uris / sizeof uris[0]; i++) {
            httpd_register_uri_handler(s_http, &uris[i]);
        }
        httpd_register_err_handler(s_http, HTTPD_404_NOT_FOUND, not_found);
    }
    dns_server_config_t dns = DNS_SERVER_CONFIG_SINGLE("*", "WIFI_AP_DEF");
    s_dns = start_dns_server(&dns);
    esp_timer_start_periodic(s_idle_timer, 10 * 1000000);
    s_active = true;
    ui_set_setup_mode(true);
    xSemaphoreGive(s_lock);
}

void web_stop(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_active) {
        esp_timer_stop(s_idle_timer);
        if (s_dns) {
            stop_dns_server(s_dns);
            s_dns = NULL;
        }
        if (s_http) {
            httpd_stop(s_http);
            s_http = NULL;
        }
        esp_wifi_stop();
        s_active = false;
        ui_set_setup_mode(false);
    }
    xSemaphoreGive(s_lock);
}

bool web_active(void)
{
    return s_active;
}
