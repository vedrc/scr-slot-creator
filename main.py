from datetime import datetime, timedelta, time
from clickupython import client
import os
from dotenv import load_dotenv, dotenv_values, set_key
import aiohttp
import asyncio
import json

def changeTimezone(new_timezone):
    set_key(".env", "TIMEZONE", new_timezone, quote_mode="never")

# gets list of all tasks in dispatching dept space
def get_tasks(c, status):
    return c.get_tasks("901504204103", subtasks=False, statuses=[status])


# converts title of task into a datetime obj
def get_time(date_list, task):
    # formatting date + removing whitespaces for ppl who mess up formatting

    name_list = task.name.split("-")
    name_list[0] = name_list[0].replace(" ", "")

    # removing existing slot tasks (will have length of 5)
    if len(name_list) != 4:
        return

    try:
        # removes DD/MM/YYYY task
        int(name_list[0][0])
    except:
        return
    
    # formats time after we've confirmed it's a valid task
    name_list[2] = name_list[2].replace(" ", "").replace("BST", "").replace("GMT", "")

    # creating datetime obj and adding to date list
    dt_obj = datetime.strptime(name_list[0] + " " + name_list[2], "%d/%m/%Y %H:%M")
    date_list.append(dt_obj)


# filters session times to only those between scheduling window
def filter_tasks(start, end, date_list):
    # converting dates into datetime
    filtered_list = []
    for date in date_list:
        if start <= date <= end:
            filtered_list.append(date)
    return filtered_list


# returns list of dates between the scheduling window to check for slots
def get_dates_between(start, end):
    dates_between = []
    delta = end-start
    for i in range(delta.days + 1):
        day = start + timedelta(days=i)
        dates_between.append(day)
    return dates_between

# finds a list of 4hr empty slots with the current sessions
def emptyslots(slotday, datetimes):
    slotday = slotday.date()

    # master list of 4hr timeslots based on the slots day
    timeslots = [ [datetime.combine(slotday, time(0, 00)), datetime.combine(slotday, time(3, 45))], 
                  [datetime.combine(slotday, time(4, 00)), datetime.combine(slotday, time(7, 45))], 
                  [datetime.combine(slotday, time(8, 00)), datetime.combine(slotday, time(11, 45))],                  
                  [datetime.combine(slotday, time(12, 00)), datetime.combine(slotday, time(15, 45))],                 
                  [datetime.combine(slotday, time(16, 00)), datetime.combine(slotday, time(19, 45))],
                  [datetime.combine(slotday, time(20, 00)), datetime.combine(slotday, time(23, 45))],
                 ]
    timeslots_boundaries = [ [time1 - timedelta(hours=2, minutes=30), time2 + timedelta(hours=2, minutes=30)] for time1,time2 in timeslots] # includes 2hr30m before and after each timeslot for adjustment calculation
    slots = [0, 0, 0, 0, 0, 0]

    todays_trainings = [dt for dt in datetimes if dt.date() == slotday] # filters down trainings to just the days trainings

    for training in todays_trainings:
        for timeslot in timeslots:
            if timeslot[0] <= training <= timeslot[1]:
                slots[timeslots.index(timeslot)] += 1
    
    empty_slots = []

    for i in range(len(slots)):
        if slots[i] == 0:
            empty_slots.append(editslot(timeslots[i], timeslots_boundaries[i], datetimes))
    return empty_slots

# edits timeslot such that conflicting trainings are accounted for
def editslot(timeslot, timeslot_boundary, trainings):
    pretime = [timeslot_boundary[0], timeslot[0]]
    posttime = [timeslot[1], timeslot_boundary[1]]
    for training in trainings:
        if pretime[0] < training and pretime[1] > training:
            timeslot[0] = training + timedelta(hours=2, minutes=30)
        elif posttime[0] < training and posttime[1] > training:
            timeslot[1] = training - timedelta(hours=2, minutes=30)
    return timeslot


async def createslot(c, start, end):
    timezone = os.getenv("TIMEZONE")
    date = start.strftime("%d/%m/%Y")
    day = start.strftime("%A")
    starttime = start.strftime("%H:%M")
    endtime = end.strftime("%H:%M")
    taskname = f"{date} - {day} - [{starttime} - {endtime}] {timezone} - Vacant"
    
    async with aiohttp.ClientSession() as session:
        # Create task from template
        async with session.post("https://api.clickup.com/api/v2/list/901504204103/taskTemplate/t-86c4v0yj5", 
                                json={ "name": taskname },
                                headers={ "accept": "application/json", "content-type": "application/json", "Authorization": API_KEY }) as response:
            data = await response.json()  # Parse the JSON response asynchronously
            taskid = data["id"]
        
        # Add tags to the task asynchronously
        tag_url_1 = f"https://api.clickup.com/api/v2/task/{taskid}/tag/training%20request"
        tag_url_2 = f"https://api.clickup.com/api/v2/task/{taskid}/tag/needs%20host"
        
        tag_tasks = [
            session.post(tag_url_1, headers={"accept": "application/json", "Authorization": API_KEY}),
            session.post(tag_url_2, headers={"accept": "application/json", "Authorization": API_KEY})
        ]
        await asyncio.gather(*tag_tasks)  # Wait for both tag requests to complete

    # Return the formatted string
    return f"**{date} {starttime} - {endtime} {timezone}**"

def init():
    # auth
    load_dotenv()
    global API_KEY
    global c
    API_KEY = os.getenv("API_KEY")
    c = client.ClickUpClient(API_KEY)

    all_tasks = get_tasks(c, "request").tasks + get_tasks(c, "pending staff").tasks + get_tasks(c, "scheduled").tasks

    unfiltered_date_list = []
    for task in all_tasks:
        if task.id == "86byavaeg":
            startdate, enddate = task.name.split("for ")[1].split(" will")[0].split(" - ") # grabs dates from timeframe message, formats, and assigns to list
        else:
            get_time(unfiltered_date_list, task)
    
    return startdate, enddate, unfiltered_date_list

async def process(startdate, enddate,unfiltered_date_list):
    startdate = datetime.strptime(startdate, "%d/%m/%y")
    enddate = datetime.combine(datetime.strptime(enddate, "%d/%m/%y"), time(23, 59))
    date_list = filter_tasks(startdate, enddate, unfiltered_date_list)

    emptyslot_list = []
    for day in get_dates_between(startdate, enddate):
        emptyslot_list.append(emptyslots(day, date_list))
    
    created_slots = []
    for day in emptyslot_list:
        for timeslot in day:
            created_slots.append(await createslot(c, timeslot[0], timeslot[1]))

    return created_slots
    
