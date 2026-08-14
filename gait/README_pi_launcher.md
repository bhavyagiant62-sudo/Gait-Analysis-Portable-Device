# Raspberry Pi auto-start setup

1. Copy the project folder to the Raspberry Pi at /home/pi/gait
2. Make the launcher executable:
   chmod +x /home/pi/gait/start_gait_app.sh
3. Copy the desktop shortcut to the desktop:
   cp /home/pi/gait/gait_dashboard.desktop /home/pi/Desktop/
4. If you want it to launch after boot, add this to the autostart file:
   echo '@/home/pi/gait/start_gait_app.sh' >> /home/pi/.config/lxsession/LXDE-pi/autostart
