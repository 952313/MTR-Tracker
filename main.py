from api import getTrains
from time import sleep
from core import mainloop
while True:
    trains = getTrains("ALL")
    mainloop(trains)
    sleep(10)