How to use snapshots.py:

    1. Download requirements.txt
    2. data.yaml has the variables (what you want to run checks on)
    3. snapshots.py is the main program, run as:
        a. 'python snapshots.py {{ MFA_USERNAME }}'
        b. 'python snapshots.py -h' for help - more to come later
    4. data.yaml is the only file to edit: 
        a. do_diff: true if you want a diff (post-maintenance) or false if not (pre-maintenance)
        b. pre_file_path / post_file_path: file names for the output files
        c. check_type: 'device' or 'circuit'
            1. device-mode: runs global checks for each device
                a. Enter in the format '- lax-agg10: junos'
            2. circuit-mode: runs checks per-circuit (more detailed than per-device)
                a. Enter in similar format to examples. 
        d. device_checks:
            1. list of devices. Ignored if 'circuit' checks
        e. global_agg: Device that will check global BGP table. Only applicable for circuit checks
        f. circuit_checks: nested dictionary format. Indentation is important!
