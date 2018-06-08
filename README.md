# ACP Autoguiding with DONUTS

Autoguiding ACP driven telescopes using DONUTS

# Setup

Clone this repository to the TCS

```sh
$> cd path/to/ag/code/home
$> git clone url/for/ag/code
```

Add and configure an instrument specific configuration file.
Use the nites or speculoos instrument files as examples

# Summary

The DONUTS package consists of several components:

**Operations:**
   1. A modified version of the ACP ```UserActions.wsc``` file. This is used to trigger autoguiding from ACP plans
   1. A daemon script ```donuts_process_handler.py```. This code runs all the time listening for commands from ACP to start and stop the guiding. The commands are triggered by the custom ```UserActions.wsc``` script above
   1. A shim ```donuts_process.py```, which ```UserActions.wsc``` calls to insert jobs into the daemon using Pyro. The ```donuts_process.py``` script can also be used to manually start and stop guiding if required (in an emergency for example)
   1. The DONUTS main autoguiding code ```acp_ag.py```. This script does all the shift measuring and telescope movements
   1. A per instrument configuration file, e.g.: ```nites.py```, ```speculoos_io.py``` etc. This file contains information such as field orientation and header keyword maps.

**Admin:**
   1. A script to calibrate the autoguiding pulseGuide command, ```calibrate_pulse_guide.py```
   1. A script to update a field's autoguider reference image with a new one, ```setnewrefimage.py```. This is used when the old image is no longer suitable and you have a new image on disc that you would like to use.
   1. A script to stop field's current autoguider reference image, ```stopcurrentrefimage.py```. This is used to remove a referene frame and let DONUTS make a new one automatically next time it observes that field.


```sh
$> Open Anaconda Prompt
$> cd C:\Users\speculoos\Documents\GitHub\DONUTS_ACP\
$> python acp_ag.py io [--debug]
```

# Schematic

![Schematic](notes/DONUTS_AG_v3.png)

# Contributors

James McCormac

# License

MIT
