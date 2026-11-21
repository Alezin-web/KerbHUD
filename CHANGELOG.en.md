## 0.17.13 — Improvement suggestions and update notice

* **Suggest an improvement:** new button in the main window and items in the Help and tray menus. It opens the project's new-suggestion page on GitHub, with a text template (including the KerbHUD version); you write and send it with your own GitHub account. KerbHUD sends nothing by itself.
* **More visible update notice:** when there is a new version, a **green banner** appears at the top of the main window ("New version X available" with "See what's new and update" and "Not now" buttons) and an item at the top of the tray menu. The tray balloon notifies once per version. "Not now" hides the banner for that version; a newer version notifies again.
* KerbHUD now re-checks every 6 hours (before, only on start), since it stays open in the tray for days. It never opens windows by itself: in the middle of a race that would take focus from the game, and installing is always your action.

## 0.17.12 — Tires: temperature first

* **Tires:** temperature is now the highlight of each tire (big number in the temperature colour + the three zones); wear is smaller, below (before, the big wear number with a bar looked like "load").
* **iRacing:** temperature now comes first from the carcass (which updates while driving); the surface one is only used if the carcass one does not exist. *Still to be confirmed in the game.*
* **Diagnostics (LMU):** now shows the raw tire values (zone temperatures, carcass, inner layer, load, pressure and ideal temperature) to check exactly what the game sends.

## 0.17.11 — Optional Standings in practice/qualy and top bar fix

* **Standings in Practice and Qualy:** new option "Practice/Qualy: hide until someone sets a lap time" (Standings Config; on by default, as before). When off, Standings shows from the start with **all drivers** (those without a time come after, with "—"), with no waiting message.
* **Top bar:** with Header L and Drivers XS the bar ran into the column titles; it now shrinks by itself just enough to fit.

## 0.17.10 — Header and driver size in Standings

* **Standings — Header size** (XS, S, M, L): changes the top bar (time, incidents, lap, drivers and the column titles). **Driver size** (XS, S, M, L): changes the driver rows and the class headers. "S" is the usual size. The top bar shrinks by itself just enough to never run into the column titles (for example Header L with Drivers XS).

## 0.17.9 — Scale by the red square and new Standings options

* **Scale without scrolling:** the mouse wheel no longer resizes anything. In edit mode, **drag the red square** (edge or corner) on Standings and Inputs: text and window change together, keeping the proportion, and the opposite side stays put. Dragging no longer removes rows or columns; use the Rows options for that. Ctrl + wheel is still transparency.
* **Standings — Rows:** "Top rows" (default 3) and "Rows around me" (default 7): **type any number you want** (up to 40). Shows the top of your class, a gap, then a window with you in the middle. Replaces the old row limit.
* **Standings — Other classes:** "top cars" and "cars near me" (default 1 and 1), also typed. **0 and 0 hides the other categories** (and their headers).
* **Standings — Font:** pick any font installed on Windows ("Default" is the current one).
* The Broadcast preset got its own counts. The window height is still the row limit.

## 0.17.8 — Seconds in the session time

* **Session time with seconds:** the top bar of Standings and Relative now shows the total with seconds too (`00:20:07 / 00:45:00`, previously `00:45m`).

## 0.17.7 — Manufacturer from the team in Le Mans Ultimate

* **Manufacturer logo in LMU:** the car name in LMU only mentions the team ("Proton Competition 2025 #99"). KerbHUD now has its own team/number → manufacturer table (cross-checked with TinyPedal's list), so Hypercars and GTs show the right brand, including teams that run different cars per class.
* Fixed: teams whose name contains a brand (e.g. "AF Corse", "Alpine Elf") in LMP2 cars were shown as Ferrari/Alpine; LMP2 is always Oreca.
* A team not in the table still gets no logo (nothing is invented); adjust it in `brand_overrides.json` — your rules always win.

## 0.17.6 — General review

* **The overlay no longer freezes on a read error:** before, any unexpected error while reading the simulator silently stopped the capture until you restarted the program. Now the error is logged, reading continues and, if it does not go away, KerbHUD reconnects by itself.
* **Error log:** new `kerbhud.log` file (Help → Open log file) to send me when something goes wrong.
* **Error-proof settings:** a corrupted or invalid `settings.json` no longer stops the app from opening (the bad file is kept as `settings.json.bad`) and it is now written safely.
* **iRacing:** odd session text no longer blocks reading. **Updater:** waits for the program to close more reliably, retries when a file is in use, deletes nothing if the copy fails and handles odd GitHub replies.
* Unused code cleanup and more tests.

## 0.17.5 — Live position on iRacing

* **Live Standings and Relative in iRacing races:** the official iRacing position only changes when a car crosses the finish line. Now, in a **race**, KerbHUD works out the order from each car's position on track (completed laps + part of the current lap), so overtakes show up right away.
* You can go back to the official position in Config → Settings → "iRacing: live race position".
* Nothing changes in practice and qualifying: there the order is by best lap, which only changes when someone completes a lap.

## 0.17.4 — iRacing Track Map

* **Track Map on iRacing without "SEM POSIÇÃO DO CARRO":** iRacing does not publish the car position, so the outline is now computed from speed and heading. Just drive **one full lap**, from one start line to the next (the accumulated error is corrected by the lap itself). Other cars are placed by their lap position.
* If the drawing comes out **mirrored** compared with the iRacing map, turn on "Mirror the track outline" in the Track Map options (module config).
* New Track Map messages: "waiting for the start line" and "lap discarded".

## 0.17.3 — Replay and Track Map on iRacing

* **"On track only" now works in replays:** on iRacing, the replay, the results screen and the gap between sessions no longer count as track (or garage). With "On track only" or "In the garage only" the overlay hides on those screens; only "Always" and DEMO show.
* **Track Map records on tracks with the pit lane along the start straight** (like Navarra): the pit lane now helps complete the outline instead of keeping it from ever finishing.
* **Track Map warning** when a lap is discarded for not closing, instead of staying stuck at the same percentage.

## 0.17.2 — Ready for GitHub

* **Updates with zero setup:** KerbHUD already knows where to look for new versions (official repository `Alezin-web/KerbHUD`). The *Repository* field in Config → Settings → Update only needs filling if you use a different one.
* **Cleaner release notes:** the "New version available" box shows the text in your language only, without markup.
* **New GitHub page:** bilingual README (Portuguese first) with images, hotkeys and FAQ.

## 0.17.1 — Isolated tests

* Fix in the automated tests only: two tests read the real SimOverlay folders on your PC and failed. No change to the program.

## 0.17.0 — Now it's KerbHUD

![KerbHUD](banner-0.17.0.png)

* **New name and new identity:** SimOverlay is now **KerbHUD** — a *kerb* is the red-and-white rumble strip of a race track. New **logo** (a K with cut corners over the kerb), icon, banners and this panel in the KerbHUD look.
* **User guide:** on the **first run** (and in *Help → User guide*) the program shows how the window works, edit mode and **every hotkey**, with an illustrated diagram.
* **Your stuff comes along:** SimOverlay's settings and data folders (logos, flags, layouts...) are **copied** to KerbHUD automatically on first run, nothing is deleted. The folder and the `.exe` are now called KerbHUD.

## 0.16.0 — Visibility, language and a free taskbar

* **"On track only" and "In the garage only" now really work:** the overlay only appears when the simulator is connected and the driver is actually on track (or in the garage). With the game closed, in the menus or without a car, **only "Always" shows it**. **DEMO mode** is always shown, whatever the rule.
* **Language:** Settings → General → *Language* (Automatic, Português or English). Applies after a restart. The README is now bilingual.
* **The overlay no longer covers the taskbar, the tray or menus:** while you use the taskbar, a tray menu or the Start menu, the overlay steps off "always on top" and returns by itself when focus goes back to the game.

## 0.15.1 — KerbHUD icon

* The **KerbHUD icon** (the logo: a K over a kerb) shows in the main window, dialogs and the **taskbar** (it would otherwise show Python's icon).
* The `.exe` uses this icon too.

## 0.15.0 — Update at a glance and what's new

![What's new](banner-0.15.0.png)

### Update
* **Version bar on the home screen:** shows the installed version and the **Check for updates** button. When there is a new version the bar says so and the button becomes **Download and install**.
* After updating, the program restarts and shows these notes.

### What's new (this panel)
* It appears the **first time** you open the window and **after every update**, showing only what changed since the last time you saw it.
* To read it again any time: **Help → What's new**.

## 0.14.0 — Widgets, data folder and updates

![Data folder](pasta-dados.png)

### Interface
* **Widgets tab:** each module with on/off, **Config** (module options, applied instantly) and a visibility rule.
* Main window with menus; closing the window **minimizes to the tray**.

### Folders
* `logos`, `flags`, `badges`, `layouts` and `tracks` now live inside **`dados`**. What you already had is **copied** automatically, nothing is deleted.

### Updates
* **Help → Check for updates**: downloads from GitHub, verifies the SHA-256 and installs, without touching the `dados` folder.

## 0.13.0 — Main window

* Main window with **Modules** and **Layouts** tabs and a status footer.
* Close = minimize to tray; **Quit** really exits.

## 0.12.0 — Settings, hotkeys and layouts

* **Settings** window (general, hotkeys, Le Mans Ultimate).
* Editable hotkeys; new: next/previous layout and skip DEMO stage.
* Layouts: rename, duplicate, export and import.
* Files to build the **.exe** (`Gerar-exe.bat`).
