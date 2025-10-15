# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.2.0)
set(toolchainVersion 14_2_Rel1)
set(picotoolVersion 2.2.0-a4)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
# Use the standard Pico board definition
set(PICO_BOARD pico CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(rpsetup C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Add executable. Default name is the project name, version 0.1

add_executable(rpsetup rpsetup.c )

pico_set_program_name(rpsetup "rpsetup")
pico_set_program_version(rpsetup "0.1")

# Define the board ID to include our serial number - will be extracted from C code
# This should match the PICO_BOARD definition in rpsetup.c

# Modify the below lines to enable/disable output over UART/USB
pico_enable_stdio_uart(rpsetup 1)
pico_enable_stdio_usb(rpsetup 1)

# Add the standard library to the build
target_link_libraries(rpsetup
        pico_stdlib)

# Add the standard include files to the build
target_include_directories(rpsetup PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
)

pico_add_extra_outputs(rpsetup)

