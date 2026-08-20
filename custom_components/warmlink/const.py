DOMAIN='warmlink'
UPDATE_INTERVAL=120

# Product IDs that identify LinkedGo smart radiators (e.g. Scantherm panel
# radiators). These speak a much smaller protocol than the heat pumps, so the
# coordinator polls RADIATOR_CODES instead of the full heat-pump codes.json.
RADIATOR_PRODUCT_IDS = {"1473911871244337152"}

# The full radiator protocol as captured from the WarmLink app (18 codes).
# R02 = target temperature (write-confirmed), T1 = current room temperature,
# Fan_Speed_Setting = heat level 1-6, Fault1 = 16-bit fault mask.
RADIATOR_CODES = [
    "Power", "Mode", "Power_Timer", "Power_Timer_Hours",
    "Fan_Speed_Setting", "Sleep",
    "R01", "R02", "R03", "R05", "R06",
    "2013", "T1", "H05", "Fault1", "O2", "O5", "H06",
]
