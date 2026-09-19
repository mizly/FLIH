################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
BSP/%.o: ../BSP/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2100/ccs/tools/compiler/ti-cgt-armllvm_5.1.1.LTS/bin/tiarmclang.exe" -c @"syscfg/device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O2 -I"C:/Users/zw/workspace_ccstheia/CarMove_USART" -I"C:/Users/zw/workspace_ccstheia/CarMove_USART/Debug" -I"C:/ti/mspm0_sdk_2_11_00_07/source/third_party/CMSIS/Core/Include" -I"C:/ti/mspm0_sdk_2_11_00_07/source" -I"C:/Users/zw/workspace_ccstheia/CarMove_USART/BSP" -gdwarf-3 -MMD -MP -MF"BSP/$(basename $(<F)).d_raw" -MT"$(@)" -I"C:/Users/zw/workspace_ccstheia/CarMove_USART/Debug/syscfg"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


