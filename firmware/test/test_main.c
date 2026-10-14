// Host unit tests for the pure-C firmware modules (UBX, geo, trip). Run: firmware/test/run.sh
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "geo.h"
#include "trip.h"
#include "ubx.h"

static int checks;
#define CHECK(c) do { checks++; if (!(c)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); return 1; } } while (0)

// Home used in the trip tests: about 1 degree latitude = 111.2 km, so 1e-7 deg ~ 1.1 cm.
#define HOME_LAT 482000000   // 48.2 N
#define HOME_LON 163700000   // 16.37 E
#define M_TO_LAT_E7(m) ((int32_t)((m) / 111195.0 * 1e7))

static trip_fix_t fix_at_m_north(double metres)
{
    trip_fix_t f = { .valid = true, .lat_e7 = HOME_LAT + M_TO_LAT_E7(metres), .lon_e7 = HOME_LON,
                     .h_acc_mm = 3000, .num_sv = 12 };
    return f;
}

static int test_geo(void)
{
    // Vienna Stephansdom -> Vienna Hauptbahnhof is about 2.3 km.
    double d = geo_distance_m(482085000, 163730000, 481852000, 163760000);
    CHECK(d > 2500 && d < 2700);
    CHECK(geo_distance_m(HOME_LAT, HOME_LON, HOME_LAT, HOME_LON) < 0.001);
    double hundred = geo_distance_m(HOME_LAT, HOME_LON, HOME_LAT + M_TO_LAT_E7(100), HOME_LON);
    CHECK(fabs(hundred - 100) < 0.5);
    return 0;
}

static int test_ubx_valset(void)
{
    // Reference frame computed by hand: set CFG-RATE-MEAS (U2) = 1000 in RAM.
    ubx_cfg_item_t items[] = { { UBX_CFG_RATE_MEAS, 1000 } };
    uint8_t buf[64];
    size_t n = ubx_build_valset(buf, sizeof buf, UBX_LAYER_RAM, items, 1);
    const uint8_t expect_head[] = { 0xB5, 0x62, 0x06, 0x8A, 0x0A, 0x00, 0x00, 0x01, 0x00, 0x00,
                                    0x01, 0x00, 0x21, 0x30, 0xE8, 0x03 };
    CHECK(n == sizeof expect_head + 2);
    CHECK(memcmp(buf, expect_head, sizeof expect_head) == 0);
    // Checksum: Fletcher-8 over class..payload.
    uint8_t a = 0, b = 0;
    for (size_t i = 2; i < n - 2; i++) { a += buf[i]; b += a; }
    CHECK(buf[n - 2] == a && buf[n - 1] == b);

    // Value sizes come from the key: L/U1 -> 1 byte, U4 -> 4 bytes.
    ubx_cfg_item_t mix[] = { { UBX_CFG_UART1_BAUDRATE, 115200 }, { UBX_CFG_UART1OUTPROT_NMEA, 0 },
                             { UBX_CFG_MSGOUT_UBX_NAV_PVT_UART1, 1 } };
    n = ubx_build_valset(buf, sizeof buf, UBX_LAYER_RAM, mix, 3);
    CHECK(n == 6 + 4 + (4 + 4) + (4 + 1) + (4 + 1) + 2);
    CHECK(buf[10] == 0x01 && buf[11] == 0x00 && buf[12] == 0x52 && buf[13] == 0x40);
    CHECK(buf[14] == 0x00 && buf[15] == 0xC2 && buf[16] == 0x01 && buf[17] == 0x00);  // 115200 LE

    // Too small a buffer is refused.
    CHECK(ubx_build_valset(buf, 10, UBX_LAYER_RAM, mix, 3) == 0);
    return 0;
}

static size_t make_frame(uint8_t *out, uint8_t cls, uint8_t id, const uint8_t *payload, uint16_t len)
{
    out[0] = 0xB5; out[1] = 0x62; out[2] = cls; out[3] = id; out[4] = len & 0xFF; out[5] = len >> 8;
    memcpy(out + 6, payload, len);
    uint8_t a = 0, b = 0;
    for (size_t i = 2; i < 6u + len; i++) { a += out[i]; b += a; }
    out[6 + len] = a; out[7 + len] = b;
    return 8u + len;
}

static int test_ubx_parse_nav_pvt(void)
{
    uint8_t pvt[UBX_NAV_PVT_LEN] = { 0 };
    pvt[20] = 3;           // 3D fix
    pvt[21] = 0x01;        // gnssFixOK
    pvt[23] = 11;          // numSV
    int32_t lon = 163700123, lat = -481234567;
    uint32_t hacc = 2500;
    memcpy(pvt + 24, &lon, 4);   // host is little-endian like the receiver
    memcpy(pvt + 28, &lat, 4);
    memcpy(pvt + 40, &hacc, 4);

    uint8_t stream[300];
    size_t n = 0;
    const char noise[] = "$GNRMC,garbage*00\r\n\xB5";   // NMEA and a stray sync byte first
    memcpy(stream, noise, sizeof noise - 1);
    n += sizeof noise - 1;
    n += make_frame(stream + n, UBX_CLASS_NAV, UBX_ID_NAV_PVT, pvt, sizeof pvt);

    ubx_parser_t p;
    ubx_parser_reset(&p);
    int frames = 0;
    ubx_nav_pvt_t out;
    for (size_t i = 0; i < n; i++) {
        if (ubx_parser_feed(&p, stream[i])) {
            frames++;
            CHECK(p.cls == UBX_CLASS_NAV && p.id == UBX_ID_NAV_PVT);
            CHECK(ubx_decode_nav_pvt(p.payload, p.len, &out));
        }
    }
    CHECK(frames == 1);
    CHECK(out.fix_type == 3 && out.fix_ok && out.num_sv == 11);
    CHECK(out.lon_e7 == lon && out.lat_e7 == lat && out.h_acc_mm == hacc);

    // A corrupted checksum is rejected.
    n = make_frame(stream, UBX_CLASS_NAV, UBX_ID_NAV_PVT, pvt, sizeof pvt);
    stream[n - 1] ^= 0xFF;
    ubx_parser_reset(&p);
    for (size_t i = 0; i < n; i++) {
        CHECK(!ubx_parser_feed(&p, stream[i]));
    }
    // Wrong length is not decoded.
    CHECK(!ubx_decode_nav_pvt(pvt, 50, &out));
    return 0;
}

static trip_config_t config(void)
{
    trip_config_t c = { .home_set = true, .home_lat_e7 = HOME_LAT, .home_lon_e7 = HOME_LON,
                        .arrive_radius_m = 150, .leave_radius_m = 300 };
    return c;
}

static int test_trip_leaving_then_arriving(void)
{
    trip_config_t c = config();
    trip_t t;
    unsigned a = trip_start(&t, &c, PARKED_HOME);
    CHECK(t.state == TRIP_LEAVING && a == TRIP_ACT_PRESS_LEAVE);

    // Underground: no fix, nothing happens. Then out of the garage, still near home.
    trip_fix_t none = { 0 };
    CHECK(trip_on_fix(&t, &c, &none) == TRIP_ACT_NONE);
    trip_fix_t near = fix_at_m_north(80);
    CHECK(trip_on_fix(&t, &c, &near) == TRIP_ACT_NONE && t.state == TRIP_LEAVING);
    // Between the radii: still leaving (hysteresis).
    trip_fix_t mid = fix_at_m_north(250);
    CHECK(trip_on_fix(&t, &c, &mid) == TRIP_ACT_NONE && t.state == TRIP_LEAVING);
    // Beyond the leave radius: away, saved.
    trip_fix_t far = fix_at_m_north(2000);
    a = trip_on_fix(&t, &c, &far);
    CHECK(t.state == TRIP_AWAY && t.parked == PARKED_AWAY && a == TRIP_ACT_SAVE_PARKED);

    // Coming back: between the radii nothing, inside the arrive radius -> arrive.
    CHECK(trip_on_fix(&t, &c, &mid) == TRIP_ACT_NONE && t.state == TRIP_AWAY);
    trip_fix_t close = fix_at_m_north(120);
    a = trip_on_fix(&t, &c, &close);
    CHECK(t.state == TRIP_ARRIVED && t.parked == PARKED_HOME);
    CHECK(a == (TRIP_ACT_SAVE_PARKED | TRIP_ACT_PRESS_ARRIVE));
    // Further fixes at home do not press again.
    CHECK(trip_on_fix(&t, &c, &near) == TRIP_ACT_NONE);
    return 0;
}

static int test_trip_boot_away_and_drive_by(void)
{
    trip_config_t c = config();
    trip_t t;
    CHECK(trip_start(&t, &c, PARKED_AWAY) == TRIP_ACT_NONE && t.state == TRIP_AWAY);
    trip_fix_t close = fix_at_m_north(100);
    CHECK(trip_on_fix(&t, &c, &close) & TRIP_ACT_PRESS_ARRIVE);
    // Drove past home without stopping: back to away, stop pressing, saved.
    trip_fix_t far = fix_at_m_north(800);
    unsigned a = trip_on_fix(&t, &c, &far);
    CHECK(t.state == TRIP_AWAY && t.parked == PARKED_AWAY);
    CHECK(a == (TRIP_ACT_SAVE_PARKED | TRIP_ACT_STOP_PRESSING));
    return 0;
}

static int test_trip_bad_fixes_and_no_home(void)
{
    trip_config_t c = config();
    trip_t t;
    trip_start(&t, &c, PARKED_AWAY);
    trip_fix_t inaccurate = fix_at_m_north(10);
    inaccurate.h_acc_mm = 80000;  // 80 m: not trusted
    CHECK(trip_on_fix(&t, &c, &inaccurate) == TRIP_ACT_NONE && t.state == TRIP_AWAY);
    trip_fix_t few = fix_at_m_north(10);
    few.num_sv = 3;
    CHECK(trip_on_fix(&t, &c, &few) == TRIP_ACT_NONE && t.state == TRIP_AWAY);

    trip_config_t nohome = c;
    nohome.home_set = false;
    CHECK(trip_start(&t, &nohome, PARKED_HOME) == TRIP_ACT_NONE && t.state == TRIP_NO_HOME);
    trip_fix_t close = fix_at_m_north(10);
    CHECK(trip_on_fix(&t, &nohome, &close) == TRIP_ACT_NONE);

    // Setting home where the car is: parked home, next start presses for leaving.
    CHECK(trip_on_home_set(&t, &c) == TRIP_ACT_NONE || t.parked == PARKED_HOME);
    CHECK(t.state == TRIP_LEAVING && t.parked == PARKED_HOME);
    trip_start(&t, &c, PARKED_AWAY);
    CHECK(trip_on_home_set(&t, &c) == TRIP_ACT_SAVE_PARKED && t.parked == PARKED_HOME);
    return 0;
}

int main(void)
{
    int fails = test_geo() + test_ubx_valset() + test_ubx_parse_nav_pvt() + test_trip_leaving_then_arriving() +
                test_trip_boot_away_and_drive_by() + test_trip_bad_fixes_and_no_home();
    printf("%s: %d checks\n", fails ? "FAILED" : "all tests passed", checks);
    return fails ? 1 : 0;
}
