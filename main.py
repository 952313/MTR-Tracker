from api import getTrains
from time import sleep
from KTLcore import mainloop
while True:
    trains = getTrains("KTL")
    mainloop(trains)
    sleep(10)