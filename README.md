# BOUNCER 
 Privacy-aware Query Processing Over Federations of RDF Datasets


Installing BOUNCER
=================

BOUNCER runs on Debian GNU/Linux and OS X and Python 3.x

1. Download BOUNCER
    Clone using git:

    `$ git clone https://github.com/SDM-TIB/BOUNCER.git`

2. Go to BOUNCER folder:

    `$ cd BOUNCER`

3. Run:

    `pip install -r requirements.txt`

4. Install BOUNCER:

    `python setup.py install`

Configure BOUNCER
================

1. Create endpoints list `endpoints.txt`

    Example:

    ```
     http://biotea.linkeddata.es/sparql
     http://colil.dbcls.jp/sparql
    ```

2. Run RDF molecule template extractor in `scripts` folder:

    `scripts$ python3.5 collect_rdfmts.py -e endpoints.txt -o json -p 'templates/mytemplates.json'`

3. Create configuration file, `config.json` in `config` folder:

    Example:

    ```
      {
      "MoleculeTemplates": [
        {
           "type": "filepath",
           "path":"templates/mytemplates.json"
             }
          ]
       }
    ```

4. Now BOUNCER is ready to "investigate" :)


About supported endpoints
------------------------

BOUNCER currently supports endpoints that answer queries either on JSON.
Expect hard failures if you intend to use BOUNCER on endpoints that answer in any other format.


Running BOUNCER
===============

Once you installed BOUNCER and the Molecule Templates are ready with config.json,
you can start running BOUNCER using the following script:

    $ python3.5 test_bouncer.py -p <planonly> -q <query> -c <path/to/config.json> -s <isstring>
    
 where:

 - `<query>`:               - SPARQL QUERY
 - `<path/to/config.json>`: - path to configuration file
 - `<isstring>`:            - (Optional) set if <query> is sent as string: available values 1 or -1. -1 is default, meaning query is from file
 - `<planonly>`:            - (Optional) if set True, then only execution plan is generated and showed. If False (default), then the generated plan will be executed, too.

 Running experiments:
 ===================

 `$./runQueries.sh <path/to/queries-dir> <path/to/config.json> <path/to/results-folder> errors.txt <planonlyTorF>  &`

 OR

 `$ python3.5 start_experiment.py -c <path/to/config.json> -q <query-file> -r <path/to/results-folder> -t 'MULDER' -s True -p <planonly> `
 
 
 References
 =========
 `Endris, Kemele & Almhithawi, Zuhair & Lytra, Ioanna & Vidal, Maria-Esther & Auer, Sören. "BOUNCER: Privacy-aware Query Processing Over Federations of RDF Datasets", (To appear)In International Conference on Database and Expert Systems Applications, DEXA 2018. `