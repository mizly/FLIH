################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS/bin/tiarmclang.exe" -c @"syscfg/device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O2 -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug" -I"C:/ti/mspm0_sdk_2_11_00_07/source/third_party/CMSIS/Core/Include" -I"C:/ti/mspm0_sdk_2_11_00_07/source" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/BSP" -gdwarf-3 -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

build-406692334: ../empty.syscfg
	@echo 'SysConfig - building file: "$<"'
	"C:/ti/sysconfig_1.26.2/sysconfig_cli.bat" -s "C:/ti/mspm0_sdk_2_11_00_07/.metadata/product.json" --script "C:/Users/zw/workspace_ccstheia/CarMove_IIC/empty.syscfg" -o "syscfg" --compiler ticlang
	@echo 'Finished building: "$<"'
	@echo ' '

syscfg/device_linker.cmd: build-406692334 ../empty.syscfg
syscfg/device.opt: build-406692334
syscfg/device.cmd.genlibs: build-406692334
syscfg/ti_msp_dl_config.c: build-406692334
syscfg/ti_msp_dl_config.h: build-406692334
syscfg/Event.dot: build-406692334
syscfg: build-406692334

syscfg/%.o: ./syscfg/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS/bin/tiarmclang.exe" -c @"syscfg/device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O2 -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug" -I"C:/ti/mspm0_sdk_2_11_00_07/source/third_party/CMSIS/Core/Include" -I"C:/ti/mspm0_sdk_2_11_00_07/source" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/BSP" -gdwarf-3 -MMD -MP -MF"syscfg/$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

startup_mspm0g351x_ticlang.o: C:/ti/mspm0_sdk_2_11_00_07/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g351x_ticlang.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS/bin/tiarmclang.exe" -c @"syscfg/device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O2 -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug" -I"C:/ti/mspm0_sdk_2_11_00_07/source/third_party/CMSIS/Core/Include" -I"C:/ti/mspm0_sdk_2_11_00_07/source" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/BSP" -gdwarf-3 -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/zw/workspace_ccstheia/CarMove_IIC/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


