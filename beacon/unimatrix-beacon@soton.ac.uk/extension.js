const St       = imports.gi.St;
const Main     = imports.ui.main;
const Mainloop = imports.mainloop;
const Lang     = imports.lang;
const Tweener  = imports.ui.tweener;
const Gtk      = imports.gi.Gtk;
const Gio      = imports.gi.Gio;

const Beacon = new Lang.Class(
{
	Name: 'Beacon',
	interval: 60,
	timeout: null,
	lastcode: -1,

	_init : function()
	{
		this.parent();
	},

	start: function()
	{
		this.checkStatus();
		Main.panel._rightBox.insert_child_at_index(this.btn, 0);
	},

	stop: function()
	{
		this.stopLoop();
    	Main.panel._rightBox.remove_child(this.btn);
  	},

	stopLoop: function()
	{
		if (this.timeout)
		{
			Mainloop.source_remove(this.timeout);
			this.timeout = null;
		}
	},

	checkStatus: function()
	{
		let file;

		file = Gio.File.new_for_path('/etc/soton/state/backup');

		file.load_contents_async(null, (file, res) =>
		{
			let contents;
			try
			{
				contents = file.load_contents_finish(res)[1].toString();
				this.bstatus = JSON.parse(contents);
				let newcode;
				newcode = this.bstatus['code']

				if (newcode == 0)
				{
					this.icon = new St.Icon({ icon_name: 'emblem-default-symbolic', style_class: 'system-status-icon' });
				}
				else if (newcode == 1)
				{
					this.icon = new St.Icon({ icon_name: 'dialog-warning-symbolic', style_class: 'system-status-icon' });
				}
				else
				{
					this.icon = new St.Icon({ icon_name: 'dialog-error-symbolic', style_class: 'system-status-icon' });
				}

				this.btn.set_child(this.icon);
			}
			catch (e)
			{
				this.icon = new St.Icon({ icon_name: 'dialog-question-symbolic', style_class: 'system-status-icon' });
				this.btn.set_child(this.icon);
			}
		});

		this.timeout = Mainloop.timeout_add_seconds(this.interval, Lang.bind(this, function()
		{
			this.checkStatus();
		}));
	},

	prep: function()
	{
		this.btn = new St.Bin({
			style_class: 'panel-button',
			reactive: true,
			can_focus: true,
			x_fill: true,
			y_fill: false,
			track_hover: true
		});

		this.icon = new St.Icon({ icon_name: 'emblem-synchronizing-symbolic', style_class: 'system-status-icon' });
		this.btn.set_child(this.icon);
		this.btn.connect('button-press-event', function() { Gtk.show_uri(null, 'https://deskctl/backup', Gtk.get_current_event_time()); });
	}
});

function init()
{
	beacon = new Beacon();
}

function enable()
{
	beacon.prep();
	beacon.start();
}

function disable()
{
	Main.panel._rightBox.remove_child(button);
	beacon.stop();
}
