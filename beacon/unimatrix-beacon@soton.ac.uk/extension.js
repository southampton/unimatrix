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

const BACKUP_PATH = '/etc/soton/state/backup';
const PUPPET_PATH = '/etc/soton/state/puppet';

const TrayMenuButton = new Lang.Class({
    Name: 'TrayMenuButton',
    Extends: PanelMenu.Button,

    _init: function() {
		// set up all the stuff
		
        this.parent(0.0, 'Status Indicator', false);

		// load the icons
		this.OKIcon=Gio.icon_new_for_string(Me.path + "/icons/ok.png");
		this.DangerIcon=Gio.icon_new_for_string(Me.path + "/icons/error.png");
		this.WarningIcon=Gio.icon_new_for_string(Me.path + "/icons/warning.png");
		this.SyncIcon=Gio.icon_new_for_string(Me.path + "/icons/sync.png");
		
		// make buttons and assign them the icons
		this.OKbutton = new St.Icon({ gicon: this.OKIcon, style_class: 'system-status-icon'});
		this.Dangerbutton = new St.Icon({ gicon: this.DangerIcon, style_class: 'system-status-icon'});
		this.Warningbutton = new St.Icon({ gicon: this.WarningIcon, style_class: 'system-status-icon'});
		this.Syncbutton = new St.Icon({ gicon: this.SyncIcon, style_class: 'system-status-icon'});
		
		// default to Danger. If it doesn't get updated then
		// something went horribly wrong anyway.
		this.currentbutton = this.Dangerbutton;

		// chuck the button on the menu bar
		this.actor.add_actor(this.currentbutton);
		
		// default text for the menu items
        backupMenuItem = new PopupMenu.PopupMenuItem(_("Backup status: "));
        // command stuff will go here
 
		puppetMenuItem = new PopupMenu.PopupMenuItem(_("Puppet status: "));
        // command stuff will go here
        
        // chuck everything in the menu
        this.menu.addMenuItem(puppetMenuItem);
        this.menu.addMenuItem(backupMenuItem);

		// all done. Run the main loop
        this.refresh();
    },
    
    refresh: function() {
		// essentially the main program loop
		
		// The timer. Once/second is the default time
        this.removeTimeout();
        this.timeout = Mainloop.timeout_add_seconds(this.refreshInterval,
            Lang.bind(this, this.refresh));
        
        // Default to Danger!
        PUPPETSTATUS = 'danger';
        BACKUPSTATUS = 'danger';
        
        // get the contents of the status files
		puppetStatus = String(GLib.file_get_contents(PUPPET_PATH)[1]);
		backupStatus = String(GLib.file_get_contents(BACKUP_PATH)[1]);
		
		// do witchcraft to parse the strings into JSON objects
		objBackup = JSON.parse(backupStatus);
        objPuppet = JSON.parse(puppetStatus);
       
		// bin everything in the menu so we can repopulate it
        this.menu.removeAll();
        
        // check the puppet status and act accordingly
        if (objPuppet.code.toString() == '0' || objPuppet.code.toString() == '2') {
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Puppet updated successfully."));
			PUPPETSTATUS = 'ok';
		} else {
			backupMenuItem = new PopupMenu.PopupMenuItem(_("Puppet update failed."));
			PUPPETSTATUS = 'warning';
		}
        
        // check the backup status and act accordingly
        if (objBackup.code == 0) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_('Backup complete.'));
			BACKUPSTATUS = 'ok';
		} else if (objBackup.code == -1) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("A backup error occured when attempting to snapshot the disk."));
			BACKUPSTATUS = 'danger';
		} else if (objBackup.code == -2) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup aborted. Network reported as down."));
			BACKUPSTATUS = 'warning';
		} else if (objBackup.code == -3) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup in progress..."));
			BACKUPSTATUS = 'sync';
		} else if (objBackup.code == 1) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup completed but some files weren't backed up."));
			BACKUPSTATUS = 'warning';
		} else if (objBackup.code == 2) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup failed. The rsync command returned an error."));
			BACKUPSTATUS = 'danger';
		} else if (objBackup.code == 3) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup failed. A python exception was generated."));
			BACKUPSTATUS = 'danger';
		} else if (objBackup.code == 100) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup failed. Python raised an exception whilst requesting backup from Plexus daemon."));
			BACKUPSTATUS = 'danger';
		} else if (objBackup.code == 101) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup failed. Python raised an exception whilst waiting for Plexus task to finish."));
			BACKUPSTATUS = 'danger';
		} else if (objBackup.code == 102) {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_("Backup failed. Python raised an exception whilst Plexus for the backup result."));
			BACKUPSTATUS = 'danger';
		} else {
			puppetMenuItem = new PopupMenu.PopupMenuItem(_('Backup status: Unknown failure state.'));
			BACKUPSTATUS = 'danger';
		}
		
		// put everything in the menu
        this.menu.addMenuItem(backupMenuItem);
        this.menu.addMenuItem(puppetMenuItem);
        
        // update the icon accordingly        
        if (PUPPETSTATUS == 'ok' && BACKUPSTATUS == 'ok') {
			this.currentbutton.set_gicon(this.OKIcon);
		}
		if (PUPPETSTATUS == 'sync' || BACKUPSTATUS == 'sync') {
			this.currentbutton.set_gicon(this.SyncIcon);
		}
		if (PUPPETSTATUS == 'warning' || BACKUPSTATUS == 'warning') {
			this.currentbutton.set_gicon(this.WarningIcon);
		}
		if (PUPPETSTATUS == 'danger' || BACKUPSTATUS == 'danger') {
			this.currentbutton.set_gicon(this.DangerIcon);
		}
        
        return true;

    },
    
    get refreshInterval() {
		// Default refresh is 1 second
        return 1;

    },
    
    removeTimeout: function() {
		// It...It needs this to work
        if (this.timeout !== undefined) {
            Mainloop.source_remove(this.timeout);
            this.timeout = undefined;
        }
    }
    
})

// actually make the trayMenu object
let trayMenu;

function init() {
	// yep
    trayMenu = new TrayMenuButton;
}

function enable() {
	// add the extension
    Main.panel.addToStatusArea('status-indicator', trayMenu);
}

function disable() {
	// kill off the extension
    trayMenu.stop();
	trayMenu.destroy();
}
