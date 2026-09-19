#include "ti_msp_dl_config.h"
#include "delay.h"
#include "usart.h"
#include "app_motor_usart.h"

#define UPLOAD_DATA 3  //0:不接受数据 1:接收总的编码器数据 2:接收实时的编码器 3:接收电机当前速度 mm/s
					   //0: Do not receive data 1: Receive total encoder data 2: Receive real-time encoder 3: Receive current motor speed mm/s

#define MOTOR_TYPE 2   //1:520电机 2:310电机 3:测速码盘TT电机 4:TT直流减速电机 5:L型520电机
                       //1:520 motor 2:310 motor 3:speed code disc TT motor 4:TT DC reduction motor 5:L type 520 motor

uint8_t times = 0;

void Car_Move(void)
{
	static uint8_t state = 0;
	switch(state)
	{
		case 0:
		Contrl_Speed(300,300,300,300);//前进 Forward
		break;
		
		case 1:
		Contrl_Speed(-300,-300,-300,-300);//后退 Back
		break;
		
		case 2:
		Contrl_Speed(600,600,-400,-400);//右旋	Rotate right
		break;
		
		case 3:
		Contrl_Speed(-400,-400,600,600);//左旋	Rotate left		
		break;
		
		case 4:
		Contrl_Speed(0,0,0,0);//停车	Stop
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
		Contrl_Pwm(1500,1500,1500,1500);//前进 Forward
		break;
		
		case 1:
		Contrl_Pwm(-1500,-1500,-1500,-1500);//后退 Back
		break;
		
		case 2:
		Contrl_Pwm(1200,1200,-1500,-1500);//右旋	Rotate right
		break;
		
		case 3:
		Contrl_Pwm(-1500,-1500,1200,1200);//左旋	Rotate left
		break;
		
		case 4:
		Contrl_Pwm(0,0,0,0);//停车	Stop
		break;
	}
	state++;
	if(state>4)state=0;
}

int main(void)
{	
	USART_Init();
	
	printf("pelase wait...\r\n");
	Contrl_Pwm(0,0,0,0);
	delay_ms(100);
	//先关闭上报	Close the report first
	send_upload_data(false,false,false);
	delay_ms(10);
	
    #if MOTOR_TYPE == 1
	send_motor_type(1);//配置电机类型	Configure motor type
	delay_ms(100);
	send_pulse_phase(30);//配置减速比 查电机手册得出	Configure the reduction ratio. Check the motor manual to find out
	delay_ms(100);
	send_pulse_line(11);//配置磁环线 查电机手册得出	Configure the magnetic ring wire. Check the motor manual to get the result.
	delay_ms(100);
	send_wheel_diameter(67.00);//配置轮子直径,测量得出		Configure the wheel diameter and measure it
	delay_ms(100);
	send_motor_deadzone(1900);//配置电机死区,实验得出	Configure the motor dead zone, and the experiment shows
	delay_ms(100);
    
    #elif MOTOR_TYPE == 2
    send_motor_type(2);
	delay_ms(100);
	send_pulse_phase(20);
	delay_ms(100);
	send_pulse_line(13);
	delay_ms(100);
	send_wheel_diameter(48.00);
	delay_ms(100);
	send_motor_deadzone(1600);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 3
    send_motor_type(3);
	delay_ms(100);
	send_pulse_phase(45);
	delay_ms(100);
	send_pulse_line(13);
	delay_ms(100);
	send_wheel_diameter(68.00);
	delay_ms(100);
	send_motor_deadzone(1250);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 4
    send_motor_type(4);
	delay_ms(100);
	send_pulse_phase(48);
	delay_ms(100);
	send_motor_deadzone(1000);
	delay_ms(100);
    
    #elif MOTOR_TYPE == 5
    send_motor_type(1);
	delay_ms(100);
	send_pulse_phase(40);
	delay_ms(100);
	send_pulse_line(11);
	delay_ms(100);
	send_wheel_diameter(67.00);
	delay_ms(100);
	send_motor_deadzone(1900);
	delay_ms(100);
    #endif
	
	//给电机模块发送需要上报的数据	Send the data that needs to be reported to the motor module
	#if UPLOAD_DATA == 1
	send_upload_data(true,false,false);delay_ms(10);
	#elif UPLOAD_DATA == 2
	send_upload_data(false,true,false);delay_ms(10);
	#elif UPLOAD_DATA == 3
	send_upload_data(false,false,true);delay_ms(10);
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
		if(g_recv_flag == 1)
		{
			g_recv_flag = 0;
			
			#if UPLOAD_DATA == 1
				Deal_data_real();
				printf("M1:%d,M2:%d,M3:%d,M4:%d\r\n",Encoder_Now[0],Encoder_Now[1],Encoder_Now[2],Encoder_Now[3]);
			#elif UPLOAD_DATA == 2
				Deal_data_real();
				printf("M1:%d,M2:%d,M3:%d,M4:%d\r\n",Encoder_Offset[0],Encoder_Offset[1],Encoder_Offset[2],Encoder_Offset[3]);
			#elif UPLOAD_DATA == 3
				Deal_data_real();
				printf("M1:%.2f,M2:%.2f,M3:%.2f,M4:%.2f\r\n",g_Speed[0],g_Speed[1],g_Speed[2],g_Speed[3]);
			#endif
		}
	}
	
}

//定时器的中断服务函数,每100ms读取数据并打印
//The timer interrupt service function reads and prints data every 100ms
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
