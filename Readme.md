Seano
=====

Seano *(a sea of notes)* is a primitive, lightweight database that automatically
associates records with the Git tags where the records where first created.

Records in a Seano database are Json objects, which are stored on disk as
distinct YAML files to improve human-readability.  The primary key of the
records is an arbitrary string, which is encoded into the filename of the YAML
file, and is colloquially referred to as the "note ID".  Note IDs are random hex
strings by default, but under the hood, they can be pretty much any
filesystem-safe string.

Seano is heavily inspired by [`reno`, written by Doug Hellmann at
OpenStack](https://docs.openstack.org/reno/), and bears a number of similarities
to it.  The main difference is that Seano is designed more for general-purpose
*(though, still lightweight)* storage, and concomitantly, is engineered to more
easily coexist with third party data formatters.

Testing Locally
---------------

Starting from scratch, this is how to set up local unit testing:

```sh
# Create and enter a virtual environment:
virtualenv .venv
. .venv/bin/activate

# Install Seano in the virtual environment in "editable mode"
pip install -e .

# Install extra dependencies needed by the unit tests:
pip install -r ci_utest_requirements.txt
```

Then, going forward, you can run unit tests like this:

```sh
pytest
```
