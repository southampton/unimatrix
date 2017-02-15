# unimatrix-zero
The server component of unimatrix. Includes backups (via ``plexus`` daemon and OpenSSH server), puppet module hosting (via ``rrsync`` and OpenSSH server), and a web application which hosts an API for ``drone`` and ``bonemeal`` to use, and a web interface for administrators. 

## API Documentation

### Version 1

*The version 1 API has not yet been finalised. Details are subject to change, but every effort will be made to not change the API unless absolutley necessary.*

#### register

- Path: ``/api/v1/register``
- Method: ``POST``
- Parameters
-- username
-- password
-- hostname

The username/password belong to the user within LDAP who wants to register the new workstation. The hostname is the name of the workstation to register. It must match the following regular expression:

``^(uos|iss|lnx|UOS|ISS|LNX)\-[0-9]{2,8}$``

The result of the API call will be JSON with a top level dictionary/hash. If an error occured the result will look something like this:

```
{
	"error": true,
	"reason": "The server was unable to generate a ssh keypair"
}
```

If no error occurs then the result will look like this:

```
{
	"private_key": "...",
	"public_key": "...",
	"backup_key": "...",
	"backup_port": "7284",
	"api_key": "..."
}
```

If the ``error`` key is sent then that can be assumed to mean something went wrong - it won't be sent in the JSON response if no error occured. 

The meaning of each of these are as follows:

- **private_key**: The SSH private key as a string, used for backups and puppet sync
- **public_key**: The SSH public key as a string
- **backup_key**: The password to use for access control to rhe rsyncd running on the workstation. 
- **backup_port:** The port which should be used to forward the local rsyncd across the SSH tunnel to the backup server
- **api_key**: The password to use when making other API calls


#### update metadata

- Path: ``/api/v1/update/metadata``
- Method: ``POST``
- Parameters
-- hostname
-- api_key
-- metadata

This method is used to store metadata about the workstation on the LDI server. This is used for reporting. 

The value of ``metadata`` should be a JSON formatted dictionary/hash.

#### update facts

- Path: ``/api/v1/update/facts``
- Method: ``POST``
- Parameters
-- hostname
-- api_key
-- facts

This method is used to store puppet facts from the workstation on the LDI server. This is used for reporting. 

The value of ``facts`` should be the JSON formatted output of ``puppet facts``.

#### update status

- Path: ``/api/v1/update/status``
- Method: ``POST``
- Parameters
-- hostname
-- api_key
-- backup
-- puppet
-- updates

This method is used to store the status of puppet, backup and software updates on the LDI server. This is used for reporting. 

The value of ``backup``, ``puppet`` and ``updates`` should be a JSON formatted string. 

#### event

- Path: ``/api/v1/event``
- Method: ``POST``
- Parameters
-- hostname
-- api_key
-- event

This method is used to alert the LDI server that an event has taken place on the workstation. Currently the value of 'event' can be one of:

- ``ping`` - the workstation is just checking in to say its alive
- ``startup`` - the workstation has started up
- ``shutdown`` - the workstation is shutting down