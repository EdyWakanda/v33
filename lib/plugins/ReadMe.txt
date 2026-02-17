You can find plugins in the "Plugin" forum in the Discord.
Making plugins requires coding knowledge and is for people that want to add their own features.


Any file that is not a python file or that starts with 2 underscores "__", will not be detected as a plugin - this is useful for adding external classes or just storing plugins you don't want to run but want to save for later.

There is an "example.py" plugin you can find in the Discord and it's basically the same as lunar lite. You can build off of this if you want to make your own.


How do plugins work?

Lunar searches this folder for any python file thats name doesn't start with 2 underscores, then looks for the necessary classes and functions (class Plugin, def setup, def on_data_received) as well as the plugin_type.

If those exist and the plugin_type is either "aim" or "overlay", lunar will start sending the model results to the "on_data_received" function instead of doing it's own calculations.


You can use some of Lunar's functions like "move", "is_pressed", etc. by using "self.api"
Example:
self.api.move(10, 10)
self.api.is_pressed(0x02)

Every frame, Lunar will send the model results and the live config to the "on_data_received" function.

Example:
def on_data_received(self, data):
        api = self.api
        if not api:
            print('Failed to connect to Lunar. Make sure you are using Lunar v2.067 or newer')
            return

	cfg = data['config']
        results = data['results']

	fov = cfg['fov']['size']
	sens = cfg['aim_settings']['sensitivity']



Plugins are a BETA feature and a prone to bugs. They are subject to change.

❤️