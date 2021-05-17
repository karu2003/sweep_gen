#!/usr/bin/python3
from scipy.signal import chirp
import numpy as np
import matplotlib.backends.backend_agg as agg
import time
import os
import sys
from decimal import Decimal  # needed to do correct temperature adjustment
import pygame
from pygame.locals import *
from pygame import event, fastevent  # fastevent is for multithreaded posts
import RPi.GPIO as GPIO
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")

Debugprt = True  # if True, some debug printing will be enabled

# -----Define some colour tuple names for shorthand use
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# --Initialize the PiTFT LCD and touchscreen
LCD_WIDTH = 320  # the width of the PiTFT in pixels
LCD_HEIGHT = 240  # the height of the PiTFT in pixels
LCD_SIZE = (LCD_WIDTH, LCD_HEIGHT)  # make it into a tuple for later


# ----- Menu/Screen Definitions
# Each dictionary describes a screen format
# Each dictionary key is a relative line value - they could be on the same physical line
# Each dictionary value item is a list for that line
# {line_value: [line_position, textsize, indent, font, text]}
# where:
# - line_value is a unique line number
# - line_position is the position of the line from the top of the screen in pixels*textsize
# - textsize is the text height in pixels
# - indent is the left indentation in pixels
# - font is an available Sysfont name in quotes or None
# - Text is the text to be shown, in quotes
# Values can be updated by the code before showing the screen

# Define a basic Splash screen
splash_screen = {
    0: [(LCD_HEIGHT / 30) / 2, 25, 30, "couriernew", "Sweep Generator ..."]
}

sweeps = {
    0: [18000, 34000, 0.004],
    1: [7000, 17000, 0.004],
    2: [12000, 24000, 0.004],
    3: [4000, 10000, 0.004],
    4: [48000, 78000, 0.004],
}

# Define the Sweep screen for normal mode
sweep_screen = {
    0: [0.2, 28, 4, "arial", "Sweep Parameters"],
    1: [1.6, 23, 4, "arial", "18.000 Hz"],
    2: [2.6, 23, 4, "arial", "34.000 Hz"],
    3: [3.6, 23, 4, "arial", "Duration s = s"],
    4: [4.6, 28, 4, None, "Sweep Time 1s"],
    5: [5.6, 28, 4, None, "18.000 Hz"],
    6: [6.6, 28, 4, None, "34.000 Hz"],
    7: [7.6, 28, 4, None, "Time (min:sec) = "],
}

# Define the main menu for menu mode
main_menu = {
    0: [0, 28, 110, None, "xxxxxxxxxx1"],
    1: [2, 28, 4, None, "xxxxxxxxxx2"],
    2: [3, 28, 4, None, "xxxxxxxxxx3"],
    3: [4, 28, 4, None, "Return"],
    4: [5, 28, 4, None, "Exit"],
}

Mmenumax = 4  # maximum number of selectable lines on main menu (1 thru 4)

# Define menu1 for the future
tempadj_menu = {
    0: [0, 28, 40, None, "xxxxxxxxxx4"],
    1: [2, 28, 4, None, "xxxxxxxxxx5"],
    2: [4, 28, 4, None, "xxxxxxxxxx6"],
    3: [14, 16, 4, None, "xxxxxxxxxx7"],
}

# Define menu2 for the future
timeadj_menu = {
    0: [0, 28, 40, None, "xxxxxxxxxx8"],
    1: [2, 28, 4, None, "xxxxxxxxxx9"],
    2: [4, 28, 4, None, "xxxxxxxxx10"],
    3: [14, 16, 4, None, "xxxxxxxxx11"],
}
# Matching time adjust values for the above menu, in seconds
Timevals = [6, 30, 60, 120, 600, 1800, 3600]

# Define button labels dictionary to go with the tempatures screen
# (right alignment is hard, hence the leading blanks and mono-spaced font)
button_menu1 = {
    0: [1.6, 18, 200, "DejavuSansMono", "     OFF->"],
    1: [8, 12, 240, "DejavuSansMono", "      UP->"],
    2: [13, 12, 240, "DejavuSansMono", "     Set->"],
    3: [18, 12, 240, "DejavuSansMono", "   Brush->"],
}

# Define button labels dictionary for menu mode
button_menu2 = {
    0: [3, 12, 245, "DejavuSansMono", "     OFF->"],
    1: [8, 12, 245, "DejavuSansMono", "      Up->"],
    2: [13, 12, 245, "DejavuSansMono", "    Down->"],
    3: [18, 12, 245, "DejavuSansMono", "  Select->"],
}


def set_run():
    global Run, button_menu1
    if Run:
        button_menu1[0][4] = "      ON->"
    else:
        button_menu1[0][4] = "     OFF->"


def set_brush():
    global Brush, button_menu1
    if Brush:
        button_menu1[3][4] = "   Brush->"
    else:
        button_menu1[3][4] = "Continue->"


# --Define a function to turn GPIO PiTFT button events into Pygame events using fastevent
# Note: This function runs in a separate thread from the main programme.
# Note: using pygame.event.post causes "video system not initialized" error
#  so we use fastevent.post, based on (very terse) pygame doc.


def gpiobut(channel):
    if channel == 17:  # check for button 1
        fastevent.post(pygame.event.Event(pygame.USEREVENT + 3, button=1))
    elif channel == 22:  # check for button 2
        fastevent.post(pygame.event.Event(pygame.USEREVENT + 3, button=2))
    elif channel == 23:  # check for button 3
        fastevent.post(pygame.event.Event(pygame.USEREVENT + 3, button=3))
    elif channel == 27:  # check for button 4
        fastevent.post(pygame.event.Event(pygame.USEREVENT + 3, button=4))


def debug_stop():
    time.sleep(5)
    sys.exit()


def make_graph():
    global raw_graph, canvas, chirp_x, chirp_y
    fig, ax = plt.subplots(figsize=(3.2, 2.4))
    plt.rcParams["font.size"] = "6"
    fig.subplots_adjust(left=0.15, bottom=0.15, right=0.97)
    ax.plot(chirp_x, chirp_y, "red")
    ax.set_xscale("log")
    plt.xlabel("Time", fontsize=6)
    ax.xaxis.set_label_coords(0.5, -0.12)
    plt.ylabel("Amplitude", fontsize=6)
    ax.yaxis.set_label_coords(-0.13, 0.5)
    fig.suptitle(
        "Sweep " + str(sweeps[sweep][0]) + "/" + str(sweeps[sweep][1]),
        fontsize=8,
        color="blue",
        y=0.95,
    )
    ax.grid(which="both", linestyle="--")
    ax.grid(which="minor", alpha=0.2)
    canvas = agg.FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    raw_graph = renderer.tostring_rgb()


def show_graph():
    global raw_graph, canvas
    Lcd.fill(BLACK)
    size = canvas.get_width_height()
    graph = pygame.image.fromstring(raw_graph, size, "RGB")
    Lcd.blit(graph, (0, 0))
    pygame.display.update()


# --Define a function to show a screen of text with button labels
# Note: text items in the screen dictionary can be changed before displaying
def show_text_menu(menuname, highlite, buttons):  # buttons can be None
    Lcd.fill(BLACK)  # blank the display
    # Build button labels first, so menu can overlap on leading blanks
    if buttons != None:  # see if there are buttons to show
        line = 0  # reset our line count for the labels
        for line in buttons:  # go through the  button line vslues
            linedata = buttons[line]
            myfont = pygame.font.SysFont(
                linedata[3], linedata[1]
            )  # use the font selected
            textsurface = myfont.render(
                linedata[4], False, WHITE, BLACK
            )  # write the text
            # show the text
            Lcd.blit(textsurface, (linedata[2], linedata[1] * linedata[0]))
            line = line + 1  # go to the next line
    # Build the rest of the menu
    line = 0  # start showing at line zero
    for line in menuname:  # go through the line values
        # get the value list from the menu dictionary
        linedata = menuname[line]
        myfont = pygame.font.SysFont(linedata[3], linedata[1])  # use the font selected
        # Build text and position & highlighting a line, if within range
        if line == highlite:  # check if we should highlight this line
            textsurface = myfont.render(
                linedata[4], False, BLACK, WHITE
            )  # highlight it
        else:
            textsurface = myfont.render(
                linedata[4], False, WHITE, BLACK
            )  # no highlight
        # add the line to the screen
        Lcd.blit(textsurface, (linedata[2], linedata[1] * linedata[0]))
        line = line + 1
    # Show the new screen
    pygame.display.update()  # show it all


# --Define a function to show the Sweep/times in text
def show_menu():  # shows menu
    Lcd.fill(BLACK)  # blank the display
    # update menu text in dictionary
    sweep_screen[1][4] = str.format("Start = " + "%.1f" % sweeps[sweep][0] + " Hz")
    sweep_screen[2][4] = str.format("Stop = " + "%.1f" % sweeps[sweep][1] + " Hz")
    sweep_screen[3][4] = str.format("Duration = " + str(sweeps[sweep][2]) + " s")
    sweep_screen[5][4] = str.format("%.1f" % sweeps[sweep][0] + " Hz")
    sweep_screen[6][4] = str.format("%.1f" % sweeps[sweep][1] + " Hz")
    sweep_screen[7][4] = str.format(
        "Time (min:sec) = " + str(Minx) + ":" + str(Secx).zfill(2)
    )
    show_text_menu(sweep_screen, None, button_menu1)  # Put it on the screen


# --Define a function to flip between temperature and graph displays
def show_flip():
    global Displayshow  # make this global
    if Displayshow == Displaytemp:  # if showing the temps,
        Displayshow = Displaygraph  # switch to showing a graph
        make_graph()  # get a current graph right now
        show_graph()  # put it on the screen
    else:  # otherwise,
        Displayshow = Displaytemp  # switch to showing temps
        show_menu()  # show the temps right now


# --Define a function to do time/temp display updates on a timer 2 pop
def Do_ttimer_updates():
    global Updtimex, Minx, Secx  # declare globals as needed
    Updtimex = Updtimex + Updinterval  # update increment to seconds
    Minx = Updtimex // 60  # get elapsed time in minutes
    Secx = Updtimex % 60  # get remainder secs elapsed


def sweep_gen():
    global chirp_x, chirp_y, g_amplitude, sound
    T = sweeps[sweep][2]
    chirp_x = np.arange(0, int(T * samplerate)) / samplerate
    chirp_y = chirp(
        chirp_x, f0=sweeps[sweep][0], f1=sweeps[sweep][1], t1=T, method="linear"
    )
    chirp_y = chirp_y * g_amplitude
    chirp_y = chirp_y.astype(np.int16)
    chirp_y = np.repeat(chirp_y.reshape(len(chirp_y), 1), 2, axis=1)
    sound = pygame.sndarray.make_sound(chirp_y)


# ----- Begin Main Programme
# --Initialize the PiTFT LCD and touchscreen
LCD_WIDTH = 320  # the width of the PiTFT in pixels
LCD_HEIGHT = 240  # the height of the PiTFT in pixels
LCD_SIZE = (LCD_WIDTH, LCD_HEIGHT)  # make it into a tuple for later
# Setup SDL system variables to use the PiTFT
os.putenv("SDL_FBDEV", "/dev/fb1")  # specify device as frame buffer1
os.putenv("SDL_MOUSEDRV", "TSLIB")  # TSLIB doesn't work too well with Stretch
# Mouse is PiTFT touchscreen
os.putenv("SDL_MOUSEDEV", "/dev/input/touchscreen")
os.putenv("SDL_AUDIODRIVER", "alsa")

sweep = 0
Run = False
Brush = True
samplerate = 192000.0
blocksize = 1024 * 4
g_amplitude = 17750  # 18550 - 3.3V P2P
chirp_x = 0
chirp_y = []
sound = []
start_idx = 0
canvas = 0
raw_graph = 0
buffer = []

# --Initialize Pygame
pygame.mixer.pre_init(frequency=int(samplerate), size=-16, channels=2, buffer=blocksize)
pygame.init()
pygame.mouse.set_visible(False)
Lcd = pygame.display.set_mode(LCD_SIZE)
fastevent.init()  # Initialize fastevents for multithreaded GPIO detect
pygame.event.set_blocked(pygame.MOUSEMOTION)
pygame.event.set_blocked(pygame.MOUSEBUTTONUP)
pygame.font.init()

sweep_gen()

# -Initialize pygame timer events
# Initialize the pygame time event and variables for recording purposes
Timeval = 0  # start sample rate at first entry in list
Tinterval = Timevals[Timeval]  # set the timer interval in msec
# Define  a pygame user event for the recording timer
pygame.time.set_timer(USEREVENT + 1, Tinterval * 1000)  # create a timer event #1

# -Initialize a pygame timer event to update the time/temperature display
Updinterval = 1  # Update interval in sec (may be longer for easier save/hold)
Updtimex = 0  # Initialize update timer value since start
pygame.time.set_timer(USEREVENT + 2, Updinterval * 1000)  # create timer event #2

# Show the splash screen - no buttons
show_text_menu(splash_screen, None, None)

GPIO.setmode(GPIO.BCM)  # use BCM chip's numbering scheme vs. pin numbers
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # PiTFT button 1
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # PiTFT button 2
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # PiTFT button 3
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # PiTFT button 4
# Define GPIO button event handlers for the PiTFT 2423
GPIO.add_event_detect(17, GPIO.FALLING, callback=gpiobut, bouncetime=300)
GPIO.add_event_detect(22, GPIO.FALLING, callback=gpiobut, bouncetime=300)
GPIO.add_event_detect(23, GPIO.FALLING, callback=gpiobut, bouncetime=300)
GPIO.add_event_detect(27, GPIO.FALLING, callback=gpiobut, bouncetime=300)

# --Initialize main variables
Minx = 0  # total time since execution started in minutes
Secx = 0  # leftover seconds for Minx:Secx display

Displaytemp = 1  # value if we're showing temperature
Displaygraph = 2  # value if we're showing a graph
Displayshow = Displaytemp  # default to show temperature initially

# init timer (sec) for mouse/touch debounce
Mousetimer = pygame.time.get_ticks() / 1000
Mousewait = 2  # choose 2 sec between MOUSEDOWN events for touch debounce
Menumode = False  # Start without a menu
Mmenuline = 1  # start with line 1 on main menu

################################################
while True:
    # ----- Handle events in non-menu mode
    while Menumode == False:  # loops waiting for events in 'normal' mode
        event = pygame.fastevent.wait()  # wait for an event object to check
        # --Handle the recording timer pop 1 event
        if event.type == pygame.USEREVENT + 1:  # using literal here for timer pop 1
            # Show graph, if that's the mode we're in
            if Displayshow == Displaygraph:  # show a graph, if required
                make_graph()  # build the graph
                show_graph()  # show the graph
        # --Handle the time/ display update for timer pop event 2
        elif event.type == pygame.USEREVENT + 2:  # using literal here for timer pop 2
            Do_ttimer_updates()  # Update the time/temp display values
            if Brush and Run:
                sound.play()
            if Displayshow == Displaytemp:  # if we're supposed to be showing the temp
                show_menu()  # Show the new time/temp screen
        # --Handle a PiTFT button is press - driven by the gpiobut GPIO callback function thread
        elif (
            event.type == USEREVENT + 3
        ):  # check for a PiTFT button press, literal value
            if Debugprt == True:
                print("button =", event.button)
            # --Check for button 1 Output ON/OFF
            if event.button == 1:  # button 1 = GPIO 17
                Run = not Run
                if Debugprt == True:
                    print("Button 1 Output ", Run)
                set_run()
                show_menu()  # show the Output ON/OFF
                if Run:
                    sweep_gen()
                    if Brush:
                        sound.play(0)
                    else:
                        sound.play(-1)
                else:
                    sound.stop()
            # --Check for button 2 - Set Sweep parameter
            elif event.button == 2:  # button 2 = GPIO 22
                sweep += 1
                sweep = sweep % len(sweeps)
                if Debugprt == True:
                    print("Button 2 set Sweep")
                    print(sweeps[sweep])
                if Displayshow == Displaytemp:
                    show_menu()
            # --Check for button 3 - switch to Menu mode
            elif event.button == 3:  # button 3 = GPIO 23
                if Debugprt == True:
                    print("Button 3 switches to Menu mode")
                # Menumode = True  # Turn on Menu Mode for future events
                # Mmenuline = 1  # start main menu with line 1 highlighted
                # # Note: Menunow is just a reference to a menu and not the contents of the menu itself
                # # This makes for easy, efficient checks for the current menu
                # Menunow = main_menu  # set the current menu, for the record
                # # Show the main menu, 1st line highlighted
                # show_text_menu(main_menu, Mmenuline, button_menu2)
            # --Check for button 4 --- Brush mode
            elif event.button == 4:  # button 3 = GPIO 27
                Brush = not Brush
                if Debugprt == True:
                    print("Button 4 Brush ", Brush)
                set_brush()
                show_menu()  # show the Brush ON/OFF
                if Brush and Run:
                    sound.stop()
                    sound.play(0)
                if not Brush and Run:
                    sound.stop()
                    sound.play(-1)
        # --Handle touchscreen events in non-menu mode ------
        # Switches display show type (graph or temp) if the screen is clicked/touched
        #   because it frees up a GPIO button for other uses
        elif event.type == pygame.MOUSEBUTTONDOWN:  # check for mouse click/touch
            # -Cleanup for noisy MOUSEBUTTON events on PiTFT, which causes problems
            # Note: Mouse position info for the touchscreen is currently useless on Stretch.
            # SDL TSLIB support used to do this stuff
            if event.button == 1:  # only watch for button 1 - touch screen filter #1
                mousetime = (
                    pygame.time.get_ticks() / 1000
                )  # get the relative time in sec
                # Ignore too many MOUSEDOWN events together - touch screen filter #2
                if (
                    mousetime - Mousetimer > Mousewait
                ):  # check if enough time has passed
                    Mousetimer = mousetime  # if so, record this last touch/click
                    show_flip()  # switch between temp and latest graph display
                    if Debugprt == True:
                        if Displayshow == Displaygraph:
                            displayshow = "Graph"
                        else:
                            displayshow = "Settings"
                    print("Touch to flip display selected. Now", displayshow)

    #############################################
    # ----- Menu Mode Event handler
    #############################################
    while Menumode == True:  # loop forever, waiting for events in 'menu' mode
        event = pygame.fastevent.wait()  # wait for an event object to check
        # --Handle the time display update timer pop event 2 in menu mode
        if event.type == pygame.USEREVENT + 2:  # using literal here for timer pop
            Do_ttimer_updates()  # Update the LED & time/temp display values
        # --Handle PiTFT button presses in menu mode driven by gpiobut GPIO callback function thread
        elif (
            event.type == USEREVENT + 3
        ):  # check for a PiTFT button press, literal value
            if Debugprt == True:
                print("menu button =", event.button)  # debug
            # --Check for button 2 - Menu mode - Up
            if event.button == 2:  # button 2 = GPIO 22
                if Debugprt == True:
                    print("Button 2 is Up")
                # -Handle Up on the main menu
                if Menunow == main_menu:  # Check if we're on the main menu
                    if Mmenuline == 1:  # if we're at the top
                        Mmenuline = Mmenumax  # roll to the bottom line
                    else:
                        Mmenuline = Mmenuline - 1  # otherwise, just go up a line
                    # show the new highlighted menu line
                    show_text_menu(main_menu, Mmenuline, button_menu2)
                # -End of Up for the main menu

                # -Handle Up in the Temperature Adjustment menu
                # Note: the following is a reference comparison and not a content comparison
                # i.e. Even if the contents of the tempadj_menu have changed it can be True
                elif Menunow == tempadj_menu:  # check if we're in the temp adjust menu
                    if Ttempadj < 10:  # upper limit is 10 for now
                        # increment Temperature adjustment
                        Ttempadj = round(Decimal(Ttempadj) + Decimal(0.1), 1)
                    tempadj_menu[2][4] = str(Ttempadj)
                    show_text_menu(tempadj_menu, 2, button_menu2)
                # -Handle Up in the Time Adjustment menu
                # chk if we're in the time adjust menu
                elif Menunow == timeadj_menu and Ttimeval < len(Timevals) - 1:
                    Ttimeval = Ttimeval + 1  # move to the next highest value
                    # show current time adjustment
                    timeadj_menu[2][4] = str(Timevals[Ttimeval])
                    # show new menu                    Timeval = Timeval - 1 #go up one item if not at the start value
                    show_text_menu(timeadj_menu, 2, button_menu2)
            # --Check for button 3 --- Down - in menu mode
            elif event.button == 3:  # Check for Down
                if Debugprt == True:
                    print("Button 3 is Down")
                # -Handle Down on main menu
                if Menunow == main_menu:  # Check if we're on the main menu
                    if Mmenuline == Mmenumax:  # if we're at the bottom
                        # roll to the top line (line 0 is the title)
                        Mmenuline = 1
                    else:
                        Mmenuline = Mmenuline + 1  # Otherwise just go to the next line
                    # show the new highlighted menu line
                    show_text_menu(main_menu, Mmenuline, button_menu2)
                # -Handle Down on the Temperature Adjustment menu - in decimal
                elif Menunow == tempadj_menu:  # Check if we're on the temp adjust menu
                    if Ttempadj > -10.0:  # lower limit is -10 for now
                        # increment Temperature adjustment
                        Ttempadj = round(Decimal(Ttempadj) - Decimal(0.1), 1)
                    # show current temperature adjustment
                    tempadj_menu[2][4] = str(Ttempadj)
                    # show new menu
                    show_text_menu(tempadj_menu, 2, button_menu2)
                # -Handle Down in Time adjustment menu
                elif (
                    Menunow == timeadj_menu and Ttimeval > 0
                ):  # chk if we're in the time adjust menu
                    Ttimeval = (
                        Ttimeval - 1
                    )  # go down one item if not at the first value
                    # show current time adjustment
                    timeadj_menu[2][4] = str(Timevals[Ttimeval])
                    # show updated menu
                    show_text_menu(timeadj_menu, 2, button_menu2)
            # --Check for button 4 --- Select, in menu mode
            elif event.button == 4:
                if Debugprt == True:
                    print("Button 4 is Select")
                # ---- Handle Select on the main menu
                if Menunow == main_menu:  # check if we're on the main menu
                    # -Handle 'Exit' selected from main menu  - always first, for debugging
                    if Mmenuline == 4:  # check for line 4 select - Exit programme
                        if Debugprt == True:
                            print("Exit Selected")
                        pygame.display.quit()  # clean up
                        sys.exit()  # exit this programme
                    # -Handle Temp Adjust selected from main menu menu
                    elif Mmenuline == 1:  # Check for Temp Adj
                        if Debugprt == True:
                            print("Selected Temp Adj menu")
                        Menunow = tempadj_menu  # update what menu we're in now
                        Ttempadj = Tempadj  # Get the current adjustment for the menu
                        # show current temperature adjustment
                        tempadj_menu[2][4] = str(Ttempadj)
                        # show new menu
                        show_text_menu(tempadj_menu, 2, button_menu2)
                    # -Handle Time Adjust selected from main menu
                    elif Mmenuline == 2:  # Check for Time Adj
                        if Debugprt == True:
                            print("Selected Time Adj menu")
                        Menunow = timeadj_menu  # update what menu we're in now
                        Ttimeval = Timeval  # Set a temporary index for menu purposes
                        # show current time adjustment
                        timeadj_menu[2][4] = str(Timevals[Ttimeval])
                        # show new menu
                        show_text_menu(timeadj_menu, 2, button_menu2)
                    # -Handle 'Return' selected from main menu
                    elif Mmenuline == 3:  # check for Return selected
                        if Debugprt == True:
                            print("Return Selected")
                        # Show updated display now, as appropriate to the mode we were in before menu mode
                        if (
                            Displayshow == Displaytemp
                        ):  # if we were showing the temperature
                            show_menu()  # show current temperature
                        # Show graph, if that's the mode we were in
                        elif Displayshow == Displaygraph:  # show a graph, if required
                            make_graph()
                            show_graph()
                        Menumode = False  # Turn off menu mode for now, as if 'Return' was selected
                # ---- Handle Select in secondary menus
                # -Handle Select in Temperature Adjustment menu
                elif Menunow == tempadj_menu:  # check if we're on the temp adjust menu
                    # Put the new adjustment value into effect
                    Tempadj = float(Ttempadj)
                    # Note: it might be good to also reset values, but there might be a need not to do this
                    Menunow = main_menu  # Update current menu to main_menu
                    show_text_menu(main_menu, Mmenuline, button_menu2)  # show it
                    if Debugprt == True:
                        print("Temp Adjust Value Selected =", Tempadj)
                # -Handle Select in Time Adjustment menu
                elif Menunow == timeadj_menu:  # check if we're in the time adj menu
                    # set the new timer interval in msec
                    Tinterval = Timevals[Ttimeval]
                    # Define an updated pygame user event for the new recording timer value
                    # create a timer event
                    pygame.time.set_timer(USEREVENT + 1, Tinterval * 1000)
                    Menunow = main_menu  # Update current menu to the main_menu
                    show_text_menu(main_menu, Mmenuline, button_menu2)  # show it
                    if Debugprt == True:
                        print("Time Adjust Selected =", Tinterval)