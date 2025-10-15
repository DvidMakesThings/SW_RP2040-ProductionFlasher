#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/unique_id.h"  // For unique board ID
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "serial_number.h"  // Include the generated header

// This pattern includes both our assigned serial number and the board's unique ID
// This helps with production tracking
const char DEVICE_ID_PATTERN[] = "DEVICE_ID:" SERIAL_NUMBER ":END";

// Storage for the unique board ID string (hex format)
char unique_board_id_str[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];

int main()
{
    // Initialize standard IO
    stdio_init_all();
    
    // Initialize the onboard LED
    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
    
    // Get the unique board ID as string
    pico_get_unique_board_id_string(unique_board_id_str, sizeof(unique_board_id_str));

    // Wait a moment for USB to initialize
    sleep_ms(2000);
    
    // Main loop
    while (true) {
        // Print a device information header
        printf("\n======== DEVICE INFORMATION ========\n");
        printf("Device Serial: %s\n", SERIAL_NUMBER);
        printf("Unique Board ID: %s\n", unique_board_id_str);
        printf("Firmware Version: %s\n", FIRMWARE_VERSION);
        printf("Build Date: %s\n", BUILD_TIMESTAMP);
        printf("===================================\n\n");

        
        sleep_ms(3000);  // Wait 3 seconds before printing again
    }
}
