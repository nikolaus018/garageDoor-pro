idf_component_register(SRCS "app.c" "geo.c" "gnss.c" "nmea.c" "presser.c" "settings.c" "trip.c" "ubx.c" "ui.c" "web.c"
                    INCLUDE_DIRS "."
                    EMBED_FILES "www/index.html"
                    PRIV_REQUIRES app_update dns_server esp_app_format esp_driver_gpio esp_driver_uart
                                  esp_event esp_http_server esp_netif esp_timer esp_wifi nvs_flash)
