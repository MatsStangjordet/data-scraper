# Running script

pip install -r requirements.txt
pythong data-scraper.py -h

# Sourcing files:
Mainframe
	Expected location of the mainframe files:
	# To be shared with mainframe (if they are unsure)
	server: 10.252.6.94
	user: pwhq1ftp
	dir /receive/ITM
		# For user of this script
		find on server using locate ITM
		create a tarball move to home directory, set permissions and sftp into this directory
Pac-data
	Reach out to PAC TEA for data extract

After a succesful run folder setup shold look like this:
total 22740
-rw-r--r--. 1 e787335 e787335    12624 Jul  6 18:00 data-scraper.py
drwxr-xr-x. 1 e787335 e787335    16770 Jul  6 13:28 ITM
drwxr-xr-x. 1 e787335 e787335     1014 Jul  6 17:49 Out_Exel_Exports_20250706
-rw-r--r--. 1 e787335 e787335 23191126 Jul  5 20:51 pac-data.xlsx
-rwxr-xr-x. 1 e787335 e787335      454 Jul  7 09:25 README.txt
-rw-r--r--. 1 e787335 e787335       16 Jul  6 13:27 requirements.txt
-rw-r--r--. 1 e787335 e787335    65748 Jul  6 18:11 script_20250706.log
