# Generic RP2040 Programming Tool

**Requirements Specification**

## 1. Introduction and Scope

This document defines the functional and non-functional requirements for a **generic RP2040 programming and provisioning tool**.

The tool is intended to support flashing, provisioning, verification, labeling, and artefact generation for RP2040-based devices during development, production, and validation phases. While the first concrete use case is an RP2040-based managed PDU, the tool shall not be architecturally coupled to any specific product, firmware, command set, or vendor naming.

Product-specific behavior shall be introduced only through configuration, templates, or profiles, not through hardcoded logic.

The scope of this document covers:

* host-side software behavior,
* supported workflows,
* data handling and traceability,
* extensibility hooks for future test and calibration stages.

Firmware implementation details are explicitly out of scope.

---

## 2. General Architecture Requirements

The tool shall be implemented in **Python** and provide a **graphical user interface** suitable for daily use on both Windows and Linux systems. The application is intended to run on developer workstations as well as dedicated HIL/SIL or factory programming stations.

The architecture shall separate:

* device detection and transport handling,
* programming backends,
* serial communication logic,
* provisioning logic,
* artefact management,
* GUI presentation.

This separation is required to allow reuse of the tool across multiple RP2040-based products with differing provisioning commands and verification logic.

---

## 3. Device Detection and Lifecycle Handling

The tool shall continuously monitor the host system for RP2040 devices entering BOOTSEL mode and appearing as USB mass storage devices.

Programming-related actions shall remain disabled until at least one compatible device is detected. Detection shall be dynamic; devices may be connected or disconnected at any time without requiring an application restart.

The design shall allow sequential programming of multiple units during a single session. Parallel programming is not required but shall not be architecturally prevented.

---

## 4. Programming Artefact and CSV-Based Control

The programming process shall be driven by a **CSV file** acting as a production artefact and traceability record.

Each row represents a logical device instance identified primarily by a serial number. The CSV contains both pre-filled fields and fields populated by the tool during the programming process.

Certain fields, such as serial number, may be pre-generated outside the tool. Other fields are entered via the GUI and remembered across sessions to reduce repetitive input.

The tool shall automatically select the next unprogrammed entry based on the absence of a programming timestamp, while still allowing manual selection of any entry for reprogramming or inspection.

Reprogramming an already programmed unit shall not overwrite historical data. Instead, the tool shall append new metadata indicating the reprogramming event, preserving traceability.

---

## 5. Firmware Upload Mechanism

Firmware shall be uploaded using **picotool** or an equivalent RP2040-compatible programming utility.

The tool shall support ELF, HEX, and UF2 firmware artefacts. Firmware paths are selectable via the GUI and may differ per product or per batch.

The programming step shall be treated as a transactional operation. Exit codes and tool output shall be captured and evaluated before proceeding to subsequent steps.

---

## 6. Serial Interface Management

After firmware upload, the RP2040 device is expected to enumerate as a serial device. The tool shall detect newly appearing serial ports and associate them with the most recently programmed device.

Transient disconnects caused by firmware-triggered resets are expected behavior. The serial handling logic shall tolerate such resets and automatically reconnect without user intervention or application instability.

A configurable timeout shall be applied if no usable serial interface becomes available.

---

## 7. Provisioning and Configuration Phase

Provisioning is defined as the process of writing device-specific configuration values into non-volatile storage on the target device after firmware upload.

The provisioning mechanism shall be command-driven over the serial interface. The exact commands, tokens, and validation responses shall be configurable per product profile.

Typical provisioning flows include:

* unlocking a provisioning mode,
* writing identity parameters such as serial number or region,
* verifying written values,
* rebooting the device.

The tool shall not assume a specific command set beyond what is provided by the selected profile.

---

## 8. Post-Programming Verification

After provisioning and reboot, the tool shall verify persistence by querying the device and parsing its responses.

Verification logic shall be declarative and profile-driven. Expected fields, acceptable values, and failure conditions must be explicitly defined.

Any mismatch between expected and reported values shall result in a failed programming state and be clearly reported to the user.

---

## 9. Label Generation and Printing

The tool shall support generation of printable labels based on vector templates.

Templates may include placeholders for serial number or other identifiers. The tool shall replace these placeholders and render the final output into a raster format suitable for printing.

Printing shall use the host operating system’s printer subsystem. Printer selection and configuration shall remain external to the tool.

Label generation shall be optional and configurable per product profile.

---

## 10. Artefact Generation and Retention

For each programmed device, the tool shall generate a dedicated artefact directory named after the device identifier.

This directory shall contain:

* a human-readable programming report,
* captured serial logs,
* generated labels,
* verification results.

The structure shall be stable and suitable for long-term retention as part of compliance or internal traceability records.

---

## 11. Future Extensions

The architecture shall explicitly reserve integration points for:

* sensor calibration,
* measurement calibration,
* automated functional testing using an external test framework.

These stages are not implemented in the initial version but shall not require architectural refactoring to add later.

---

## 12. Non-Goals

This tool is not responsible for:

* firmware compilation,
* cloud-based data storage,
* device fleet management after deployment.
