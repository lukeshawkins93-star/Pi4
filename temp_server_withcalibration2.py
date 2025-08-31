import requests
from datetime import date
import time
import io
import sqlite3

import sys

#Could/Should calibrate all thermocouples when I have a more solid plan
#Could test them using dry block (pizza stone) in oven
cal1=-3
cal2=.1
cal3=-.4
cal4=-3.3

db_filename = sys.argv[1]
db_notes = sys.argv[2]
print(sys.argv[2:100])
print(sys.argv[1])

filename=sys.argv[1]
filename_str= ','.join(str(filename) for filename in filename)
filename_str2 = filename_str.replace(",", "")
notes = sys.argv[2:100]
notes_str = ' '.join(str(notes) for notes in notes)

start_time=time.time()

conn = sqlite3.connect(filename_str2)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS smoker_test (
        Minutes REAL,
        temp1 REAL,
        temp2 REAL,
        temp3 REAL,
        temp4 REAL,
        notes TEXT
     )
 ''')
c.execute("INSERT INTO smoker_test (minutes, temp1, temp2, temp3, temp4, notes) VALUES (?,?,?,?,?,?)", (('0', 0,0,0,0,notes_str)))

conn.commit()

def thermometer_main():
    filename = setup_files()
    try:
        while True:
            datapoint = collect_data()
            save_data(datapoint, filename)

    except KeyboardInterrupt:
        1==1

def setup_files():
    current_date = date.today()
    filename = f'{current_date.strftime("%Y-%m-%d")}'
    open(f'{filename}.txt', 'a')
    return filename

def collect_data():
    thermometer_api = "http://192.168.254.161"
    response = requests.get(thermometer_api)
    string_list = response.text.split(",")
    elapsed_seconds = time.time() - start_time
    elapsed_minutes = elapsed_seconds / 60
    var1, var2, var3, var4 = [float(x) for x in string_list]
    var1a=round(var1+cal1,1)
    #print(round(var1+cal1,1), round(var2+cal2,1), round(var3+cal3,1), round(var4+cal4,1))
    print(f"MEAT(F):{var1a} AIR(F):{round(var2+cal2,1)} Time(Min):{round(elapsed_minutes,2)}", end="\r", flush=True)
    var1=round(var1+cal1,1)
    var2=round(var2+cal2,1)
    var3=round(var3+cal3,1)
    var4=round(var4+cal4,1)
    csv_file = io.StringIO(response.text)
    c.execute("INSERT INTO smoker_test (minutes, temp1, temp2, temp3, temp4) VALUES (?,?,?,?,?)", (float(elapsed_minutes),float(var1),float(var2), float(var3), float(var4)))
    #print(round(elapsed_minutes,2))
    conn.commit()
    return response.text

def save_data(datapoint, filename):
    with open(f'{filename}.txt', 'a') as data_file:
        print(datapoint, file=data_file)

if __name__ == '__main__':
    thermometer_main()