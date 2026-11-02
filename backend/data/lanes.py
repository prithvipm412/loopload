"""Contract section 5 flows; hero exceptions live only in the scenario."""

def seasonal_lanes():
    groups = [
        ('Onions', ['NSK'], ['DEL','KOL','CHE','BLR','HYD'], 'open_body', [10,11,12,1]),
        ('Cotton bales', ['RJK','AMD'], ['TPR','CBE'], 'open_body', [10,11,12,1,2,3]),
        ('Textiles', ['TPR','SRT'], ['DEL','MUM','KOL','JAI'], 'container', []),
        ('Oranges', ['NAG'], ['DEL','BLR','HYD','CHE'], 'open_body', [11,12,1,2]),
        ('Marble', ['JAI'], ['BLR','HYD','MUM','PUN'], 'open_body', []),
        ('Machinery / auto parts', ['PUN','CHE'], ['DEL','BLR','AMD','LDH'], 'container', []),
        ('FMCG', ['MUM','DEL','KOL'], ['JAI','HYD','BLR'], 'container', [9,10,11]),
        ('Steel', ['RPR','VTZ'], ['HYD','BLR','CHE','NAG'], 'open_body', []),
        ('Wheat', ['LDH','KNP'], ['BLR','HYD','MUM'], 'open_body', [4,5,6]),
        ('Spices', ['COK'], ['DEL','MUM','AMD'], 'container', []),
        ('Pharma', ['HYD','AMD'], ['DEL','MUM','CHE'], 'reefer', []),
    ]
    return [dict(origin=a, destination=b, commodity=c, truck_type=t, peaks=p)
            for c, origins, destinations, t, p in groups
            for a in origins for b in destinations if a != b]
