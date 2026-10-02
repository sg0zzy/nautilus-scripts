#!/usr/bin/env python3
# GUI batch rename: Paste the selected file list, type one new name per line,
# then Rename (original extension kept; logs to rename_files.log).
# Requires Debian packages: python3-tk

import os
import tkinter as tk
import tkinter.font
import logging
from pathlib import Path


logging.basicConfig(filename='rename_files.log', level=logging.DEBUG)
# logging.debug('This message should go to the log file')
# logging.info('So should this')
# logging.warning('And this, too')
# logging.error('And non-ASCII stuff, too, like Øresund and Malmö')


# TODO pick a file list in input and rename them with an edit text
# TODO Import for the listbox


class MyTextBox:
    def __init__(self, master):

        self.master = master
        master.geometry("1300x2000")
        master.title(" file names input ")

        # FontInput = tk.new_font('mono', 16, 'normal')
        mainFont = tkinter.font.Font(family="Courier", size=12, weight="normal", slant="roman")
        labelFont = tkinter.font.Font(family="Courier", size=15, weight="normal", slant="roman")

        if os.getenv('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS') is None:
            files = "/example/flac/01.Track 1.flac\n/example/flac/02.Track 2.flac"
        else:
            files = os.getenv('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS')

        logging.debug('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS is: ' + files)

        for path in files.splitlines():
            logging.debug('adding ' + path)


        label_1 = tk.Label(text = "Input", font = labelFont)
        txt_input = tk.Text(master, height = 20,
                        width = 90,
                        bg = "light yellow",
                        font = mainFont)
        
        label_2 = tk.Label(text = "Pattern", font = labelFont)
        txt_pattern= tk.Text(master, height = 20,
                        width = 90,
                        bg = "light green",
                        font = mainFont)
        
        txt_output = tk.Text(master, height = 20,
                    width = 90,
                    bg = "light cyan",
                    font = mainFont)
        
        button_rename = tk.Button(master, height = 2,
                        width = 20,
                        text ="Rename",
                        font=mainFont,
                        command = lambda:Process_input())

        button_paste = tk.Button(master, height = 2,
                        width = 20,
                        text ="Paste",
                        font=mainFont,
                        command = lambda:Populate_input(files.splitlines()))
        
        label_1.pack()
        txt_input.pack()
        label_2.pack()
        button_paste.pack()
        txt_pattern.pack()
        button_rename.pack()
        txt_output.pack()

        def populate_input_row(row):
            logging.debug('populate_input_row: ' + row)
            txt_input.insert(tk.END, row)

        def Populate_input(myArray):
            # text = self.selection_get(selection='CLIPBOARD')
            # txt_output.insert('insert', text)
            for ii,jj in enumerate(myArray):
                logging.debug('Populate_input ' + myArray[ii])
                txt_input.insert(tk.END, myArray[ii] + "\n")


        def Process_input():
            # NAUTILUS_SCRIPT_SELECTED_FILE_PATHS
            
            INPUT = txt_input.get("1.0", "end-1c").splitlines()
            # INPUT.format
            # print(INPUT)
            PATTERN = txt_pattern.get("1.0", "end-1c").splitlines()
            # input = INPUT.splitlines()
            # pattern = PATTERN.splitlines()
            print("PATTERN is" + str(PATTERN))
            logging.debug("len(INPUT.splitlines() is: " +  str(len(INPUT)))
            if  len(INPUT) == len(PATTERN):
                for ii,jj in enumerate(INPUT):
                    # rename files
                    logging.debug("INPUT[ii] is: " + INPUT[ii])
                    logging.debug("PATTERN[ii] is: " + PATTERN[ii])
                    print("INPUT[ii] is: " + INPUT[ii])
                    print("PATTERN[ii] is: " + PATTERN[ii])
                    p = Path(INPUT[ii])
                    logging.debug('p.parent is: ' + str(p.parent))
                    logging.debug('p.name is: ' + str(p.name))
                    logging.debug('p.suffix is: ' + str(p.suffix))
                    path_new_name = Path(p.parent, f"{PATTERN[ii]}{p.suffix}")
                    logging.debug('newname is: ' + str(path_new_name))
                    p.rename(path_new_name)

                    # txt_output.insert(tk.END, p.parent + p.name)
                    txt_output.insert(tk.END, str(path_new_name) + '\n')
            else:
                txt_output.insert(tk.END,"input and pattern have different rows number")


def pippo():
    logging.debug('### START ###')
    root = tk.Tk()
    my_gui = MyTextBox(root)
    root.mainloop()


def main():
# popup a listtext
# list comprehension

# check that list number == elnum(getenv('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS','').splitlines())

    for path in os.getenv('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS','').splitlines():
        try:
            pass
            # exif_data = Image.open(path)._getexif()
        except OSError:
            continue

        try:
            pass
            # date = datetime.datetime.strptime(exif_data[DATETIME_ORIGINAL], '%Y:%m:%d %H:%M:%S')
            # directory = os.path.join(date.strftime('%Y'), date.strftime('%B'))
        except (KeyError, ValueError, TypeError):
            pass

        # os.makedirs(directory, exist_ok=True)
        # os.rename(path, os.path.join(directory, os.path.basename(path)))

if __name__ == '__main__':
    pippo()