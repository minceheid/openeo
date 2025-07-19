{% include 'app_top.tpl' %}

<style type="text/css">
	@import url("static/settings.css");
</style>

<div class="settings">
	<form>
		{% for setting in settings %}
			<div class="setting-row">
				{% if setting['type'] == 'heading' %}
					<div class="setting-heading">
						<span>{{ setting['text'] }}</span>
					</div>
				{% else %}
					<div class="setting-item">
						<label for="settings-{{ setting['id'] }}" onclick="toggleDetail('settings-detail-{{ setting['id'] }}');">{{ setting['name'] }}</label>
						<div class="settings-detail" id="settings-detail-{{ setting['id'] }}">
							{{ setting['note'] }}
						</div>
					</div>
					<div class="setting-adjuster">
						{% if setting['type'] == 'textinput' %}
							<input type="text" id="settings-{{ setting['id'] }}" name="{{ setting['id'] }}" value="{{ setting['value'] }}">
						{% endif %}
						{% if setting['type'] == 'boolean' %}
							<input type="radio" id="settings-{{ setting['id'] }}-True" name="{{ setting['id'] }}" value="True" {{ 'checked' if (setting['value']|int) else '' }}>
							<label for="settings-{{ setting['id'] }}-True">Yes</label>
							<input type="radio" id="settings-{{ setting['id'] }}-False" name="{{ setting['id'] }}" value="False" {{ '' if (setting['value']|int) else 'checked' }}>
							<label for="settings-{{ setting['id'] }}-False">No</label>
						{% endif %}
						{% if setting['type'] == 'number' %}
							<input type="number" id="settings-{{ setting['id'] }}-True" name="{{ setting['id'] }}" value="{{ setting['value'] }}" min="{{ setting['range'][0] }}" max="{{ setting['range'][1] }}" step="{{ setting['step'] }}">
						{% endif %}
						{% if setting['type'] == 'slider' %}
							<input type="range" id="settings-{{ setting['id'] }}-True" name="{{ setting['id'] }}" value="{{ setting['value'] }}" min="{{ setting['range'][0] }}" max="{{ setting['range'][1] }}" step="{{ setting['step'] }}">
						{% endif %}
					</div>
				{% endif %}
			</div>
		{% endfor %}
	</form>
</div>

<script type="text/javascript" src="static/settings.js"></script>
	
{% include 'html_footer.tpl' %}