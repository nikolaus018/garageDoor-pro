// Setup Wi-Fi (open soft AP "GarageDoor-XXXX", no password), captive portal and the web panel at
// http://192.168.4.1. Turns itself off after 10 minutes without panel activity.
#pragma once

#include <stdbool.h>

#define WEB_IDLE_TIMEOUT_S 600

void web_init(void);
void web_start(void);
void web_stop(void);
bool web_active(void);
