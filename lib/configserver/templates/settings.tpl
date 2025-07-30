{% include 'app_top.tpl' %}

<style type="text/css">
	@import url("static/settings.css");
</style>

<div class="settings">
	<form method="POST" autocomplete="off" action="/setsettings">
		{% for setting in settings %}
			<div class="setting-row {{ 'setting-cat-end' if (setting['type'] == 'catend') else '' }}">
				{% if setting['type'] == 'heading' %}
					<div class="setting-heading">
						<span>{{ setting['text'] }}</span>
					</div>
				{% elif setting['type'] == 'catend' %}
					&nbsp;
				{% else %}
					<div class="setting-item">
						<label for="settings-{{ setting['id'] }}" onclick="toggleDetail('settings-detail-{{ setting['id'] }}');">{{ setting['name'] }}</label>
						<div class="settings-detail" id="settings-detail-{{ setting['id'] }}">
							{{ setting['note'] }}
						</div>
					</div>
					<div class="setting-adjuster">
						{% if setting['type'] == 'textinput' %}
							<input type="text" id="settings-{{ setting['id'] }}" name="{{ setting['id'] }}" value="{{ setting['value'] }}" {{ ('pattern="' + setting['pattern'] + '"') if setting['pattern']|length >= 1 else "" }}>
							<span></span>
						{% endif %}
						{% if setting['type'] == 'boolean' %}
							<input type="radio" id="settings-{{ setting['id'] }}-True" name="{{ setting['id'] }}" value="True" {{ 'checked' if (setting['value']|int) else '' }}>
							<label for="settings-{{ setting['id'] }}-True">Yes</label>
							<input type="radio" id="settings-{{ setting['id'] }}-False" name="{{ setting['id'] }}" value="False" {{ '' if (setting['value']|int) else 'checked' }}>
							<label for="settings-{{ setting['id'] }}-False">No</label>
							<span class="setting-radio-space"></span>
						{% endif %}
						{% if setting['type'] == 'number' %}
							<input type="number" id="settings-{{ setting['id'] }}" name="{{ setting['id'] }}" value="{{ setting['value'] }}" min="{{ setting['range'][0] }}" max="{{ setting['range'][1] }}" step="{{ setting['step'] }}">
							<span></span>
						{% endif %}
						{% if setting['type'] == 'slider' %}
							<span id="settings-{{ setting['id'] }}-slider-value">{{ setting['value'] }}</span>
							<span id="settings-{{ setting['id'] }}-slider-unit">{{ setting['value_unit'] }}</span>
							<input type="range" id="settings-{{ setting['id'] }}" name="{{ setting['id'] }}" value="{{ setting['value'] }}" 
								   min="{{ setting['range'][0] }}" max="{{ setting['range'][1] }}" step="{{ setting['step'] }}"
								   oninput="document.getElementById('settings-{{ setting['id'] }}-slider-value').innerHTML = this.value;">
							<span></span>
						{% endif %}
						{% if setting['type'] == 'url' %}
							<input type="url" id="settings-{{ setting['id'] }}" name="{{ setting['id'] }}" value="{{ setting['value'] }}" pattern="{{ setting['pattern'] }}">
							<span></span>
						{% endif %}
					</div>
				{% endif %}
			</div>
		{% endfor %}
		
		<div class="setting-buttons">
			<input type="submit" value="Save Settings">
		</div>
	</form>
</div>

<script type="text/javascript" src="static/settings.js"></script>
	
{% include 'html_footer.tpl' %}