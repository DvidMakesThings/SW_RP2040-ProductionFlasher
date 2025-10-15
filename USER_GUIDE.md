# User Guide: Raspberry Pi Pico Build & Program Tool

## Introduction

This guide explains how to use the Raspberry Pi Pico Build & Program Tool in easy-to-understand steps. This tool helps you:

1. Build your code for the Raspberry Pi Pico
2. Flash your code to the Pico
3. Keep track of multiple Picos with unique serial numbers

You don't need to be a programming expert to use this tool!

## Getting Started

### What You Need

- A computer with Python 3.6 or newer
- Raspberry Pi Pico SDK installed
- A Raspberry Pi Pico device
- USB cable to connect your Pico

### Basic Steps for Building and Flashing

#### Step 1: Open a Terminal

Open PowerShell (on Windows) or Terminal (on Mac/Linux) and navigate to your project folder.

#### Step 2: Build Your Code

To build your code, run:

```
py -3 FlashApp/RP_flasher.py --configure --build
```

This configures and compiles your code into a format that the Pico can understand.

#### Step 3: Flash Your Code to the Pico

1. Hold the BOOTSEL button on your Pico
2. Connect the Pico to your computer with the USB cable
3. Release the BOOTSEL button
4. The Pico should appear as a USB drive
5. Run:

```
py -3 FlashApp/RP_flasher.py --flash
```

You can also combine configuration, building, and flashing in a single command:

```
py -3 FlashApp/RP_flasher.py --program
```

After flashing, the tool will automatically verify the device via its serial port to confirm the correct serial number and firmware version.

If you want to skip this verification step:
```
py -3 FlashApp/RP_flasher.py --flash your_firmware.uf2 --skip-verify
```

Your code is now running on the Pico!

#### Step 4: All-in-One Command

To build and flash in one step:

```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --all
```

## Production Programming

When you're making multiple Picos with the same code but want each to have a unique serial number, use production programming.

### Setting Up Serial Numbers

1. Create a spreadsheet of serial numbers using the included CSV file.
2. Each row represents one device.
3. Empty date_programmed fields mean the serial number is still available.

Example of serial_numbers.csv:
```
serial_number,date_programmed,firmware_version,programmed_by,batch_id,notes
PICO-001,2023-10-15,0.9.0,developer,BATCH0001,Initial test unit
PICO-002,2023-10-15,0.9.0,developer,BATCH0001,Development unit
PICO-003,,,,BATCH0002,Available for use
```

### Programming with Serial Numbers

#### Step 1: Check Available Serial Numbers

To see which serial numbers are available and which have been used:

```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --list-devices
```

#### Step 2: See Which Serial Number is Next

```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --next-serial
```

#### Step 3: Program a Device

1. Put your Pico in BOOTSEL mode (hold BOOTSEL while connecting)
2. Run:

```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv
```

The production programming process follows these steps:

1. **Preparation**: Loads configuration and finds the next available serial number
2. **Clean**: Cleans the build directory to ensure no old cached files remain
3. **Configure**: Generates a header file with the serial number and configures the build
4. **Compile**: Builds the firmware with the embedded serial number
5. **Prepare for Upload**: Ensures the UF2 file includes the serial number
6. **Upload**: Uploads the firmware to the connected Pico
7. **Verify**: Verifies the device is working with the correct serial number via serial port monitoring
8. **Update Database**: Marks the serial number as used in the CSV file
9. **Complete**: Reports successful programming

If you want to skip the serial verification step:
```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --skip-verify
```

The tool uses picotool to flash the device, providing a more reliable programming experience.

The tool uses picotool to flash the device, providing a more reliable programming experience.

#### Step 4: Add More Information

You can add more details when programming:

```
py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --firmware-version 1.1.0 --programmed-by "Your Name"
```

## Understanding Serial Numbers

When you use production programming:

1. The tool creates a header file (serial_number.h) with your unique serial number
2. This header is placed in your project directory during building
3. Your program can use the `SERIAL_NUMBER` constant to identify itself
4. The date and who programmed it are saved in your CSV file

### How to Use the Serial Number in Your Code

To actually use the serial number in your program, you need to:

1. Include the header file in your C code by adding this line at the top of your file:
   ```c
   #include "serial_number.h"
   ```

2. Use the `SERIAL_NUMBER` constant wherever you need it:
   ```c
   printf("Device Serial Number: %s\n", SERIAL_NUMBER);
   ```

Here's a complete example of how to modify your rpsetup.c file:

```c
#include <stdio.h>
#include "pico/stdlib.h"
#include "serial_number.h"  // Include the generated header

int main()
{
    stdio_init_all();

    while (true) {
        // Print the serial number along with other information
        printf("Hello from device %s!\n", SERIAL_NUMBER);
        sleep_ms(1000);
    }
}
```

### Complete Production Programming Workflow

Here's a step-by-step workflow for programming multiple devices:

1. **Setup**:
   - Create your serial_numbers.csv file with unique serial numbers for each device
   - Prepare your serial_number.h.template file
   - Make sure your C code includes "serial_number.h" and uses the SERIAL_NUMBER constant

2. **Programming Session**:
   - Check which serial numbers are available: 
     ```
     py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --list-devices
     ```
   
   - For each device to program:
     1. Connect the Pico while holding BOOTSEL button
     2. Run: 
        ```
        py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --firmware-version X.Y.Z --programmed-by "Your Name"
        ```
     3. The tool will:
        - Get the next available serial number
        - Generate the header file with that serial number
        - Build the project with the serial number included
        - Flash the firmware to the device
        - Mark the serial number as used in the CSV
     4. Disconnect the programmed device
     5. Connect the next device and repeat

3. **Verification**:
   - After programming all devices, check the CSV file to see all programmed devices:
     ```
     py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --list-devices
     ```
   
   - To identify a specific device, connect it in BOOTSEL mode and run:
     ```
     py -3 FlashApp/RP_flasher.py --identify-device
     ```
   
   - For complete device details, use:
     ```
     py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --identify-device --production serial_numbers.csv
     ```
     
   - This works by reading the serial number directly from the header file embedded in the device's flash memory

## Common Problems and Solutions

### Pico Not Found

**Problem**: The tool says it can't find your Pico.

**Solution**: 
1. Make sure your Pico is connected via USB
2. Check that it's in BOOTSEL mode (hold BOOTSEL button while connecting)
3. The Pico should appear as a USB drive named "RPI-RP2"

### Already Programmed Warning

**Problem**: The tool warns that the device seems to already have firmware.

**Solution**:
1. Use the `--force` flag to flash anyway: 
   ```
   py -3 FlashApp/RP_flasher.py --flash firmware.uf2 --force
   ```
2. Or for production programming:
   ```
   py -3 FlashApp/RP_flasher.py --production serial_numbers.csv --force
   ```

### Serial Number Mismatch

**Problem**: The tool reports a "Serial number mismatch" error after flashing.

**Solution**:
1. This means the device already has a different serial number programmed.
2. If you want to reprogram the device with a new serial number:
   ```
   py -3 FlashApp/RP_flasher.py --production serial_numbers.csv --reprogram
   ```
3. The `--reprogram` flag tells the tool to allow changing the device's serial number.
4. Without this flag, the tool prevents accidental serial number changes to avoid confusion.

1. If you're sure you want to overwrite the existing firmware, use:
   ```
   py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --deploy --force
   ```
   or for production:
   ```
   py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --force
   ```

### Build Errors

**Problem**: The build fails with errors.

**Solution**:
1. Read the error messages to understand what went wrong
2. Fix any issues in your code
3. Run `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --clean` to clean the build folder
4. Try building again

## Quick Reference

### Basic Commands

- Build: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project`
- Flash: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --deploy`
- Build and flash: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --all`
- Clean and rebuild: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --clean --rebuild`

### Production Commands

- Program with serial number: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv`
- List devices: `py -3 FlashApp/RP_flasher.py --project-dir /path/to/your/project --production serial_numbers.csv --list-devices`
- Show next serial: `py -3 RP_flasher.py --production serial_numbers.csv --next-serial`

### Advanced Commands

- Flash a specific UF2 file: `py -3 RP_flasher.py --flash your_file.uf2`
- Use a different config: `py -3 RP_flasher.py --config my_config.py`
- Show detailed output: `py -3 RP_flasher.py -v`