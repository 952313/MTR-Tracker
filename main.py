from api import getTrains
from time import sleep
from core import mainloop
while True:
    trains = getTrains("TWL")
    mainloop(trains)
    sleep(5)