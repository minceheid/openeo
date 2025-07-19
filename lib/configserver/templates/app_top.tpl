<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>openeo Configuration Page</title>
	<link rel="stylesheet" href="static/base_style.css">
</head>
<body>
	<noscript>Warning: openeo requires Javascript to be enabled</noscript>
	<div class="top-objects-flex">
		<div class="top-icons-logo">
			<div class="burger-box" id="burgerBox">
				<div class="burger-icon"></div>
				<ul class="burger-list">
					<li><a href="/home.html">Home</a></li>
					<li><a href="/settings.html">Settings</a></li>
					<li><a href="/statistics.html">Statistics</a></li>
				</ul>
			</div>
			<div class="logo" id="logo">
				<div class="logo-inner">
					<a href="https://github.com/minceheid/openeo">
						<span class="logo-text">openeo</span>
						<img src="static/openeo_vector_glyph_lightmono.svg" width="50" height="50"/>
					</a>
				</div>
			</div>
		</div>
		<div class="top-status">
			<div class="minimal-status" id="minimalStatus">
				<p><span id="evseName" class="evse-name"></span></p>
				<p><span id="modeName" class="mode-name"></span></p>
			</div>
		</div>
		<div class="mode-switch" id="modeSwitchContainer">
			<!-- Icons from Heroicons (MIT Licence) -->
			<div class="mode-inner" id="modeSwitchSchedule">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-6 svg-use-fill" aria-labelledby="schedule-text-hidden" id="btn-sel-schedule">
					<path fill-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 0 0 0-1.5h-3.75V6Z" clip-rule="evenodd" />
				</svg><span class="hidden" id="schedule-text-hidden">Schedule</span>
			</div>
			<div class="mode-inner" id="modeSwitchManual">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-6 svg-use-fill" aria-labelledby="manual-text-hidden" id="btn-sel-manual">
					<path fill-rule="evenodd" d="M12 2.25a.75.75 0 0 1 .75.75v9a.75.75 0 0 1-1.5 0V3a.75.75 0 0 1 .75-.75ZM6.166 5.106a.75.75 0 0 1 0 1.06 8.25 8.25 0 1 0 11.668 0 .75.75 0 1 1 1.06-1.06c3.808 3.807 3.808 9.98 0 13.788-3.807 3.808-9.98 3.808-13.788 0-3.808-3.807-3.808-9.98 0-13.788a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd" />
				</svg><span class="hidden" id="manual-text-hidden">Manual</span>
			</div>
			<div class="mode-inner" id="modeSwitchRemote">
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6 svg-use-stroke" aria-labelledby="remote-text-hidden" id="btn-sel-remote">
					<path stroke-linecap="round" stroke-linejoin="round" d="M8.288 15.038a5.25 5.25 0 0 1 7.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 0 1 1.06 0Z" />
				</svg><span class="hidden" id="remote-text-hidden">Remote</span>
			</div>
		</div>
	</div>
	<div class="toast-msg-container" id="toastMsgContainer">
		<div class="toast-msg" id="toastMsg"></div>
	</div>