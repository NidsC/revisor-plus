REVISORPLUS — PARENT SUMMARY TAB
================================

WHAT CHANGED
------------
The parent summary is no longer mixed into the student dashboard.

There are now two tabs at the top:

  Student dashboard | Parent summary

STUDENT DASHBOARD
-----------------
Keeps the pupil-focused experience:
- today's mission
- target school
- simple stats
- subject progress
- topics to level up
- wins
- homework

PARENT SUMMARY
--------------
A separate, very simple one-screen view showing:
- target progress
- overall accuracy
- questions done
- homework left
- strongest subject
- areas needing focus
- subject snapshot
- the single best thing to do next

The tab works entirely in the template, so no new Django route or view is needed.

INSTALL
-------
Drag the included "templates" folder into:

F:\revisor-plus-main\revisor-plus-main

Replace:

templates\practice\dashboard.html

If the server is not running:

python main.py runserver

DIRECT LINK
-----------
The parent tab also uses the URL hash:

#parent-summary

So once the dashboard is loaded, switching to Parent summary updates the URL.
