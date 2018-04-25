Enabling Donuts triggering from ACP

   1. Renamed the old UserActions script to UserActions.wsc.20180424
   1. Registered the new script. Got error about using {} instead of () in 1 if statement. Fixed this and pushed new version. This registered with success.
   1. The TAG line stopped the target being recognised - STOPPED

It was late so I stopped the above. Today (20180425) I started testing on NITES:

   1. Made a modified version of UserActions, UserActionsNites.wsc
   1. Registered this and confirmed that the old Geostat script was displaced
   1. Tested the script and found a bug with how start/stop were supplied, fixed that
   1. Script works well
   1. TargetEnd doesn't seem to be called though (at least not for BIAS and DARK, maybe for Targets?). Will leave this in and test on sky to be sure.
   1. Included a stopDonuts in the ScriptEnd for safety
   1. Tested hopping between Donuts=on and Donuts=off, this was fine
   1. Tweaked donuts_process.py to touch empty file for each start/stop
   1. Tested code on nites and things look good.
   1. Tweaked the speculoos UserActions script to match and renamed it.


To do:

   1. Test new script on Io
   1. Add db table for when donuts starts and stops
   1. Look into the multi-threaded donuts approach
