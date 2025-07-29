<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>openeo {{ title }} &middot; {{ status['charger_name'] }}</title>
	<link rel="stylesheet" href="static/base_style.css">
	<link rel="apple-touch-icon" href="static/openeo_icon_apple.png">
</head>
<body>
	<noscript>Warning: openeo requires Javascript to be enabled</noscript>
	<div class="top-objects-flex">
		<div class="top-icons-logo">
			<div class="burger-box" id="burgerBox">
				<div class="burger-icon" id="burgerIcon">☰</div>
				<ul class="burger-list" id="burgerMenu">
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
				<p><span id="evseName" class="evse-name">&nbsp;{{ status['charger_name'] }}&nbsp;</span></p>
				<p><span id="modeName" class="mode-name"></span></p>
			</div>
		</div>
		{% include 'mode_switch.tpl' %}
	</div>
	<div class="toast-msg-container" id="toastMsgContainer">
		<div class="toast-msg" id="toastMsg"></div>
	</div>