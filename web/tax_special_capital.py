"""Independent TY2025 Schedule D Tax Worksheet for verified 1099-DIV gains.

Sources: IRS 2025 i1040sd.pdf pages15-16; continuous-use i1099div.pdf
boxes2a/2b/2d. No original software program, table, image or source is included.
The caller supplies independently validated taxable income and IRS ordinary tax.
"""
from decimal import Decimal, ROUND_HALF_UP

SOURCES={'i1040sd':'https://www.irs.gov/pub/irs-pdf/i1040sd.pdf',
         'i1099div':'https://www.irs.gov/pub/irs-pdf/i1099div.pdf'}
ZERO={'single':48350,'mfj':96700,'mfs':48350,'hoh':64750,'qss':96700}
FIFTEEN={'single':533400,'mfj':600050,'mfs':300000,'hoh':566700,'qss':600050}
TWENTY_FIVE={'single':197300,'mfj':394600,'mfs':197300,'hoh':197300,'qss':394600}

def whole(value):return int(Decimal(value).quantize(Decimal(1),rounding=ROUND_HALF_UP))

def tax(taxable,qualified,total_gain,collectibles,unrecaptured_1250,status,ordinary_tax):
    """Actual 47-line worksheet; no losses, 4952 election, QSBS or foreign stacking.

    Box2a includes boxes2b/2d. Every argument is an already rounded form line;
    raw payer cents must be summed before the caller rounds these amounts.
    """
    values=(taxable,qualified,total_gain,collectibles,unrecaptured_1250)
    if status not in ZERO or any(type(v)is not int or v<0 for v in values):
        raise ValueError('Schedule D special-rate inputs require nonnegative whole-dollar form lines and a supported filing status.')
    # Validate the component/total relation on RAW cents in the caller. Separate
    # IRS line rounding can make the two component lines exceed the total by $1;
    # worksheet line12 explicitly uses the smaller of lines9 and11.
    lines={i:0 for i in range(1,48)}
    lines.update({1:taxable,2:qualified,6:qualified,7:total_gain,9:total_gain,
                  10:qualified+total_gain,11:collectibles+unrecaptured_1250})
    lines[12]=min(lines[9],lines[11]);lines[13]=lines[10]-lines[12]
    lines[14]=max(0,lines[1]-lines[13]);lines[15]=ZERO[status]
    lines[16]=min(lines[1],lines[15]);lines[17]=min(lines[14],lines[16])
    lines[18]=max(0,lines[1]-lines[10]);lines[19]=min(lines[1],TWENTY_FIVE[status])
    lines[20]=min(lines[14],lines[19]);lines[21]=max(lines[18],lines[20]);lines[22]=lines[16]-lines[17]
    if lines[1]!=lines[16]:
        lines[23]=min(lines[1],lines[13]);lines[24]=lines[22]
        lines[25]=max(0,lines[23]-lines[24]);lines[26]=FIFTEEN[status]
        lines[27]=min(lines[1],lines[26]);lines[28]=lines[21]+lines[22]
        lines[29]=max(0,lines[27]-lines[28]);lines[30]=min(lines[25],lines[29])
        lines[31]=whole(Decimal(lines[30])*Decimal('.15'));lines[32]=lines[24]+lines[30]
        if lines[1]!=lines[32]:
            lines[33]=lines[23]-lines[32];lines[34]=whole(Decimal(lines[33])*Decimal('.20'))
            if unrecaptured_1250:
                lines[35]=min(lines[9],unrecaptured_1250);lines[36]=lines[10]+lines[21]
                lines[37]=lines[1];lines[38]=max(0,lines[36]-lines[37])
                lines[39]=max(0,lines[35]-lines[38]);lines[40]=whole(Decimal(lines[39])*Decimal('.25'))
            if collectibles:
                lines[41]=lines[21]+lines[22]+lines[30]+lines[33]+lines[39]
                lines[42]=lines[1]-lines[41];lines[43]=whole(Decimal(lines[42])*Decimal('.28'))
    lines[44]=ordinary_tax(lines[21],status)
    lines[45]=lines[31]+lines[34]+lines[40]+lines[43]+lines[44]
    lines[46]=ordinary_tax(lines[1],status);lines[47]=min(lines[45],lines[46])
    return lines[47],{'tax_year':2025,'method':'2025 Schedule D Tax Worksheet','form_lines':{str(k):v for k,v in lines.items()},
                     'ordinary_income':lines[21],'taxable_income':taxable,'qualified_dividends':qualified,
                     'total_capital_gain_distributions':total_gain,'collectibles_28_gain':collectibles,
                     'unrecaptured_1250_gain':unrecaptured_1250,'tax_at_25_percent':lines[40],
                     'tax_at_28_percent':lines[43],'sources':dict(SOURCES),
                     'scope':'Verified1099-DIV distributions without trades/losses/carryovers/4952 election/1202 exclusions/foreign stacking'}
