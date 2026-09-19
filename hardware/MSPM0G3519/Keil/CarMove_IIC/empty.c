#include "ti_msp_dl_config.h"
#include "delay.h"
#include "usart.h"
#include "bsp_motor_iic.h"

#define UPLOAD_DATA 1  //1:接收总的编码器数据 2:接收实时的编码器
					   //1: Receive total encoder data 2: Receive real-time encoder

#define MOTOR_TYPE 2   //1:520电机 2:310电机 3:测速码盘TT电机 4:TT直流减速电机 5:L型520电机
                       //1:520 motor 2:310 motor 3:speed code disc TT motor 4:TT DC reduction motor 5:L type 520 motor

uint8_t times = 0;

void Car_Move(void)
{
	static uint8_t state = 0;
	switch(state)
	{
		case 0:
		control_speed(300,300,300,300);//前进 Forward
		break;
		
		case 1:
		control_speed(-300,-300,-300,-300);//后退 Back
		break;
		
		case 2:
		control_speed(600,600,-400,-400);//右旋	Rotate right
		break;
		
		case 3:
		control_speed(-400,-400,600,600);//左旋	Rotate left		
		break;
		
		case 4:
		control_speed(0,0,0,0);//停车	Stop
		break;
	}
	state++;
	if(state>4)state=0;
}

void Car_Move_PWM(void)
{
	static uint8_t state = 0;
	switch(state)
	{
		case 0:
		control_pwm(1500,1500,1500,1500);//前进 Forward
		break;
		
		case 1:
		control_pwm(-1500,-1500,-1500,-1500);//后退 Back
		break;
		
		case 2:
		control_pwm(1200,1200,-1500,-1500);//右旋	Rotate right
		break;
		
		case 3:
		control_pwm(-1500,-1500,1200,1200);//左旋	Rotate left
		break;
		
		case 4:
		control_pwm(0,0,0,0);//停车	Stop
		break;
	}
	state++;
	if(state>4)state=0;
}

int main(void)
{
    USART_Init();

	printf("please wait...");
    control_pwm(0,0,0,0);
    delay_ms(100);
	
    #if MOTOR_TYPE == 1
	Set_motor_type(1);//配置电机类型	Configure motor type
	delay_ms(100);
	Set_Pluse_Phase(30);//配置减速比 查电机手册得出	Configure the reduction ratio. Check the motor manual to find out
	delay_ms(100);
	Set_Pluse_line(11);//配置磁环线 查电机手册得出	Configure the magnetic ring wire. Check the motor manual to get the result.
	delay_ms(100);
	Set_Wheel_dis(67.00);//配置轮子直径,测量得出		Configure the wheel diameter and measure it
	delay_ms(100);
	Set_motor_deadzone(1900);//配置电机死区,实验得出	Configure the motor dead zone, and the experiment shows
	delay_ms(100);
    
    #elif MOTOR_TYPE == 2
    Set_motor_type(2);
	delay_ms(100);
	Set_Pluse_Phase(20);
	delay_ms(100);
	Set_Pluse_line(13);
	delay_ms(100);
	Set_Wheel_dis(48.00);
	delay_ms(100);
	Set_motor_deadzone(1600);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 3
    Set_motor_type(3);
	delay_ms(100);
	Set_Pluse_Phase(45);
	delay_ms(100);
	Set_Pluse_line(13);
	delay_ms(100);
	Set_Wheel_dis(68.00);
	delay_ms(100);
	Set_motor_deadzone(1250);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 4
    Set_motor_type(4);
	delay_ms(100);
	Set_Pluse_Phase(48);
	delay_ms(100);
	Set_motor_deadzone(1000);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 5
    Set_motor_type(1);
	delay_ms(100);
	Set_Pluse_Phase(40);
	delay_ms(100);
	Set_Pluse_line(11);
	delay_ms(100);
	Set_Wheel_dis(67.00);
	delay_ms(100);
	Set_motor_deadzone(1900);
	delay_ms(100);
    #endif
	
	//清除定时器中断标志	Clear the timer interrupt flag
    NVIC_ClearPendingIRQ(TIMER_0_INST_INT_IRQN);
    //使能定时器中断	Enable timer interrupt
    NVIC_EnableIRQ(TIMER_0_INST_INT_IRQN);
	
	while(1)
	{
		if(times>=25)//定时器每100ms累加一次，当达到25次，即2.5秒的时候转换一次小车的状态	The timer accumulates every 100ms, and when it reaches 25 times, that is, every 2.5 seconds, the state of the car is changed.
		{
			#if MOTOR_TYPE == 4
            Car_Move_PWM();
            #else
			Car_Move();
            #endif
			times = 0;
		}
		#if UPLOAD_DATA == 1
		Read_ALL_Enconder();
		printf("M1:%d\t M2:%d\t M3:%d\t M4:%d\t \r\n",Encoder_Now[0],Encoder_Now[1],Encoder_Now[2],Encoder_Now[3]);
		#elif UPLOAD_DATA == 2
		Read_10_Enconder();
		printf("M1:%d\t M2:%d\t M3:%d\t M4:%d\t \r\n",Encoder_Offset[0],Encoder_Offset[1],Encoder_Offset[2],Encoder_Offset[3]);
		#endif
	}
	
}

//定时器的中断服务函数,每100ms中断一次
//The timer's interrupt service function interrupts once every 100ms
void TIMER_0_INST_IRQHandler(void)
{
    //如果产生了定时器中断	If a timer interrupt occurs
    switch( DL_TimerG_getPendingInterrupt(TIMER_0_INST) )
    {
        case DL_TIMER_IIDX_ZERO://如果是0溢出中断	If it is 0 overflow interrupt
			times++;
			break;

        default:
            break;
    }
}
