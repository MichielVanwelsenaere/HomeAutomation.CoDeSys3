## Getting started guide (é!COCKPIT runtime)

### __Getting to know CoDeSys3__
If you have experience with programming in CodeSys3 you can skip this part. Otherwise, it's advised to gain some experience by checking the sources below:

- Setup environment and creation first project: [YouTube video](https://www.youtube.com/watch?v=hI8t9UHPV8s)
- CoDeSys start guide (uses CoDeSys 2.3 but principles still applicable): [YouTube playlist](https://www.youtube.com/watch?v=WP9pUfBi6Pw&list=PL08CDB741463CA7B4&index=1)
- CoDeSys Sequential Function Charts Explained: [YouTube video](https://www.youtube.com/watch?v=eP42t9O5drk)
- Getting to know the IEC 61131-3 standard: [iec 61131-3 reference](https://bitbucket.org/ntphx/iec-61131)

### __Setup CoDeSys 3S__

1. Download é!COCKPIT from the [WAGO website](https://www.wago.com/global/automation-technology/discover-software/ecockpit-engineering-software). 

### __Open the project__

1. open the file with *.ecp* extension in in é!COCKPIT.

### __Libraries__

1. Go to the *Library Manager* &rarr; *Libary repository* menu:

<img src="./_img/GettingStartedGuide/LibraryRepository.png" alt="LibraryRepository" width="750"/>

2. install all libraries from the [src/Libraries](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/tree/master/src/Libraries) folder.

<img src="./_img/GettingStartedGuide/installLibraries_écockpit.png" alt="Install libraries é!cockpit" width="750"/>


### __Build__

1. Build the project

<img src="./_img/GettingStartedGuide/écockpitbuild.png" alt="écockpitbuild" width="500"/>

### __Uploading and running the project__
To upload and run the project on your PLC perform the following steps:
1. From the menu, select *online* and then *login*:</br>
<img src="./_img/GettingStartedGuide/UploadToPLC.png" alt="select online and then login" width="600"/>

1. Select *Login with download* and press *OK*:</br>
<img src="./_img/GettingStartedGuide/UploadToPLC_options.png" alt="login with download" width="600"/>

1. *Start* the application on your PLC:</br>
<img src="./_img/GettingStartedGuide/UploadToPLC_start.png" alt="start the application" width="400"/>

Note that you might need to rescan your network from the *Device Communications* tab to execute these steps successfully. In addition make sure that the physical switch on your PLC is in _'RUN'_ mode (if applicable).