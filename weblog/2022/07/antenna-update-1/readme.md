---
Date: 2022-07-11 19:02:05
Tags: Ham Radio, Antennas
---

# Random Wire Antenna Update

You may recall that earlier this year I was beginning to think about a new wire antenna for the new QTH. Well now that most of the drama and exhaustion associated with moving has settled down, I’ve had a chance to work on this again. (Being off the air for nearly two months has been painful, to say the least.)

![img1](https://cdn.some.pics/mihobu/641a04bbd0723.jpg)

The new place has two very nice trees that are just about 75 feet apart. This was quite a revelation because I had previous underestimated the distance by at least 20 feet! I also revised my thinking on the antenna’s configuration as well, opting now for an inverted-L  rather than an straight line. This would give me extra length and allow me to keep the [9:1 unun](https://palomar-engineers.com/antenna-products/baluns-and-ununs/1-8-30-mhz-balunsununs/hf-high-power-balunsununs/hf-91-transformers/Bullet-50-450-9-1-HF-Balun-1-8-61-MHz-500-1500-Watts-T2FD-BBTD-ALE-p133084125) low to the ground for better accessibility. I also decided to try running a separate counterpoise, rather than relying on the coax braid. I will probably still need a common mode choke, which is not shown in the diagram.

With help from an [old friend](https://www.qrz.com/db/N8QLB) and the [best antenna-raising aid ever invented](https://www.amazon.com/gp/product/B00VO29BS0), we had polyester lines up in the trees in no time! I attached the end of the 92-foot random wire to the line using a black nylon dogbone-style insulator and hoisted it up. I don't have reliable measurement for the height, but I figure it’s up around 25 feet. For the other tree (left side of the diagram above) I fed the other end of the wire through a [small plastic pulley](https://www.mastrant.com/on-line-shop/product/5423-pulley-up-to-3-mm,-plastic-stainless) from the fine folks at Mastrant and hoisted that up, also to around 25 feet.
By the way, the wire I’m using is [JetStream 14 gauge super flexible stranded antenna wire](https://store2.rlham.com/shop/catalog/product_info.php?products_id=75223) that I bought from R&L at this year's Dayton Hamvention.

![img2](https://cdn.some.pics/mihobu/641a04d948039.jpg)

The photo is not too great, but you can just make out the length of wire. My initial tests with the [RigExpert analyzer](https://rigexpert.com/products/antenna-analyzers/) suggest that the wire might need to be trimmed a bit, but otherwise look pretty good. I haven’t connected up the rig yet, but I hope to do that later this week. I’m cautiously optimistic that I’ll be back on the air soon!

## I almost forgot...

It was important to me to be able to validate the wire lengths suggested by Palomar Engineering and other sources. Fortunately, this work had been previously done by Mike Markowski AB3AP, and I was able to borrow heavily from him. I made a slight tweak to his code to compute and plot the midpoints in the “acceptable” ranges, as shown here.

![img3](https://cdn.some.pics/mihobu/641a04ed46f6d.png)

As you can see, these numbers are basically the same as you find elsewhere. But I was surprised that the 92 foot number often found is actually at the high end of a range that goes from roughly 89 to 92 feet, with the midpoint closer to 91. That might explain why my 92 foot wire (which is actually closer to 93 feet) might need to be trimmed some. I will work on it more this week and let you know.


