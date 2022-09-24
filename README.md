## HBNet is still under heavy development and currently undergoing a partiaql rewrite. Documentation is being added to the Wiki as I write it, so check perodically to see if there is any new information. V1.0 will be ready in the next few months. See [here](https://github.com/kf7eel/hbnet/discussions/33) for the development news.

![ ](https://raw.githubusercontent.com/kf7eel/hblink3/hbnet/HBNet.png  "Logo")

HBNet is a fork of [HBlink3](https://github.com/HBLink-org/hblink3) that extends the functionality of HBLink through several features, making it more of a usable application and less of a framework. HBNet aims to be complete and ready to use application that can be used to build and run a DMR network.

HBNet consists of 2 parts, HBNet Web Service and the actual DMR server, based on HBLink. The HBNet Web Service handles user administration, server configuration, and is a content management system for your DMR network.

This project originally started as a not so simple set of scripts to decode GPS locations and generate APRS positions. Through other modifications and additions, it has grown into a fully featured fork.


### User end features:

* Handles user registration and email verification

* Individual hotspot passphrases for each user

* Automatic retrieval of DMR IDs on registration

* Automatically generate talkgroup pages

* Automatically generates a script for Pi-Star setup (WORK IN PROGRESS)

* Map of currently connected peers


### Administrative features:

* Administrate multiple DMR servers through a single web service

* Optional manual approval of new users

* Multiple Admin user logins


### OpenBridge additions

* Enhanced unit call routing between connected servers. Every server known which server every subscribers is on.

* Optionally encrypt data sent over OpenBridge


### Data Gateway (APRS/SMS)

* Compatable with HBNet and original HBLink.

* Connect your server via OpenBridge or MMDVM.

* Decodes GPS positions and generates APRS positions

* Simple web dashboard



### Other features

* SQLite or MySQL backend

* APRS and SMS features (WORK IN PROGRESS)

---
### FOR SUPPORT, DISCUSSION, GETTING INVOLVED ###

Please join the DVSwitch group at groups.io for online forum support, discussion, and to become part of the development team.

DVSwitch@groups.io 

A voluntary registry for HBlink systems with public access has been created at http://hblink-register.com.es Please consider listing your system if you allow open access.

---

### Git Repositories

[https://codeberg.org/kf7eel/hbnet](https://codeberg.org/kf7eel/hbnet)

[https://gitea.com/kf7eel/hbnet](https://gitea.com/kf7eel/hbnet)

[https://linux.us.org/HBNet/HBNet](https://linux.us.org/HBNet/HBNet)

[https://gitlab.com/hbnet2/hbnet](https://gitlab.com/hbnet2/hbnet)

[https://github.com/kf7eel/hbnet](https://github.com/kf7eel/hbnet) 



---
## PROJECT: Open Source HomeBrew Repeater Proctol Client/Master. ##

**UPDATES:**

**PURPOSE:** Thanks to the work of Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT we have an open protocol for internetworking DMR repeaters. Unfortunately, there's no generic client and/or master stacks. This project is to build an open-source, python-based implementation. You are free to use this software however you want, however we ask that you provide attribution in some public venue (such as project, club, organization web site). This helps us see where the software is in use and track how it is used.

For those who will ask: This is a piece of software that implements an open-source, amateur radio networking protocol. It is not a network. It is not intended to be a network. It is not intended to replace or circumvent a network. People do those things, code doesn't.
  
**PROPERTY:**  
This work represents the author's interpretation of the HomeBrew Repeater Protocol, based on the 2015-07-26 documents from DMRplus, "IPSC Protocol Specs for homebrew DMR repeater" as written by Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT, also licenced under Creative Commons BY-NC-SA license.

**WARRANTY**
None. The owners of this work make absolutely no warranty, express or implied. Use this software at your own risk.

**PRE-REQUISITE KNOWLEDGE:**  
This document assumes the reader is familiar with Linux/UNIX, the Python programming language and DMR.  

**MORE DOCUMENTATION TO COME**

***0x49 DE N0MJS***

Copyright (C) 2016-2020 Cortney T. Buffington, N0MJS n0mjs@me.com

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
