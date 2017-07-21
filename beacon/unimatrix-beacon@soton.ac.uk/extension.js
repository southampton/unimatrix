const St = imports.gi.St;
const Me = imports.misc.extensionUtils.getCurrentExtension();
const Gio = imports.gi.Gio;
const Main = imports.ui.main;
const Clutter = imports.gi.Clutter;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const Lang = imports.lang;
const GLib = imports.gi.GLib;
const Mainloop = imports.mainloop;
const ExtensionUtils = imports.misc.extensionUtils;
const Util = imports.misc.util;
const Gtk      = imports.gi.Gtk;

const BACKUP_PATH      = '/etc/soton/state/backup';
const REFRESH_INTERVAL = 30;

const SeparatorMenuItem = new Lang.Class({
	Name: 'SeparatorMenuItem',
	Extends: PopupMenu.PopupBaseMenuItem,
	_init: function (text) {
		this.parent({ reactive: false, can_focus: false});
		this._separator = new St.Widget({ style_class: 'popup-separator-menu-item', y_expand: true, y_align: Clutter.ActorAlign.CENTER });
		this.actor.add(this._separator, { expand: true });
	},
});

const TrayMenuButton = new Lang.Class(
{
	Name: 'TrayMenuButton',
	Extends: PanelMenu.Button,

	_init: function()
	{
		this.parent(0.0, 'Status Indicator', false);
		this.icon = new St.Icon({ icon_name: 'emblem-synchronizing-symbolic', style_class: 'system-status-icon' });
		this.actor.add_actor(this.icon);
		backupMenuItem = new PopupMenu.PopupMenuItem(_("Backup status: "));
		this.menu.addMenuItem(backupMenuItem);
		this.refresh();
	},

	refresh: function()
	{
		this.removeTimeout();
		this.timeout = Mainloop.timeout_add_seconds(REFRESH_INTERVAL, Lang.bind(this, this.refresh));

		backupStatus = String(GLib.file_get_contents(BACKUP_PATH)[1]);
		objBackup = JSON.parse(backupStatus);
	
		// check the backup status and act accordingly
		if (objBackup.code === 0)
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_('Last backup succeeded'));
			this.icon.set_icon_name('emblem-default-symbolic');
		}
		else if (objBackup.code == -2)
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Network unavailable, cannot run backup"));
			this.icon.set_icon_name('network-wired-no-route-symbolic');
		}
		else if (objBackup.code == -3)
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Backup in progress"));
			this.icon.set_icon_name('emblem-synchronizing-symbolic');
		}
		else if (objBackup.code == -4)
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Backups are disabled"));
			this.icon.set_icon_name('action-unavailable-symbolic');
		}
		else if (objBackup.code == 1)
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Backup complete, but some files could not be backed up"));
			this.icon.set_icon_name('dialog-warning-symbolic');
		}
		else
		{
			backupMenuItem = new PopupMenu.PopupMenuItem(_('The last backup failed'));
			this.icon.set_icon_name('dialog-error-symbolic');
		}

		this.menu.removeAll();
		this.menu.addMenuItem(backupMenuItem);
		this.spacer = new SeparatorMenuItem();
		this.menu.addMenuItem(this.spacer);
		let settingsMenuItem = new PopupMenu.PopupMenuItem(_('Open Desktop Manager'));
		this.menu.addMenuItem(settingsMenuItem);
		settingsMenuItem.connect('activate', function() { Gtk.show_uri(null, 'https://deskctl/backup', Gtk.get_current_event_time()); });
		let refreshMenuItem = new PopupMenu.PopupMenuItem(_('Refresh status'));
		this.menu.addMenuItem(refreshMenuItem);
		refreshMenuItem.connect('activate', Lang.bind(this, this.refresh));

		//return true;
	},

	removeTimeout: function()
	{
		if (this.timeout !== undefined)
		{
			Mainloop.source_remove(this.timeout);
			this.timeout = undefined;
		}
	}

});

function enable()
{
	trayMenu = new TrayMenuButton();
	Main.panel.addToStatusArea('status-indicator', trayMenu);
}

function disable()
{
	trayMenu.destroy();
}
