// Titan Adaptive Compute Loom v1 - parametric, low-voltage bench enclosure
// Units: millimetres. Generic board envelopes only; verify selected hardware,
// connector clearances, thermal limits and fastener locations before fabrication.
// Rendered CAD concept is not a certified electrical enclosure.

$fn = 48;
L = 260;
W = 180;
H = 58;
wall = 3;
floor_t = 4;
corner_r = 8;
show_lid = false;
show_modules = true;
show_cable_guides = true;

module rounded_box(x,y,z,r) {
    hull() for (xx=[r,x-r], yy=[r,y-r])
        translate([xx,yy,0]) cylinder(h=z,r=r);
}

module tray() {
    difference() {
        rounded_box(L,W,H,corner_r);
        translate([wall,wall,floor_t])
            rounded_box(L-2*wall,W-2*wall,H+1,corner_r-wall/2);
        // Front service opening
        translate([35,-1,14]) cube([190,wall+2,28]);
        // Rear airflow slots
        for (x=[18:12:L-18])
            translate([x,W-wall-1,18]) cube([5,wall+2,24]);
        // Side ventilation
        for (z=[14:10:44], x=[25:18:L-25])
            translate([x,-1,z]) cube([8,wall+2,3]);
        // Four enclosure mounting holes
        for (x=[14,L-14], y=[14,W-14])
            translate([x,y,-1]) cylinder(h=floor_t+2,d=4.5);
    }
}

module board_standoffs(x,y,bx,by,spacing=10) {
    for (dx=[spacing,bx-spacing], dy=[spacing,by-spacing])
        translate([x+dx,y+dy,floor_t])
            difference() {
                cylinder(h=8,d=7);
                translate([0,0,-1]) cylinder(h=10,d=2.7);
            }
}

module generic_compute_node(x,y) {
    color([0.16,0.22,0.29])
        translate([x,y,floor_t+8]) cube([94,72,2]);
    board_standoffs(x,y,94,72,9);
    // connector clearance envelope
    color([0.35,0.42,0.5])
        translate([x+4,y+72,floor_t+8]) cube([86,8,12]);
}

module power_distribution(x,y) {
    color([0.58,0.27,0.18])
        translate([x,y,floor_t+8]) cube([72,42,2]);
    board_standoffs(x,y,72,42,7);
    // terminal / fuse clearance blocks
    for (i=[0:3])
        translate([x+8+i*15,y+12,floor_t+10]) cube([10,18,8]);
}

module network_switch(x,y) {
    color([0.18,0.36,0.27])
        translate([x,y,floor_t+8]) cube([72,42,12]);
    board_standoffs(x,y,72,42,7);
    for (i=[0:4])
        translate([x+8+i*12,y+42,floor_t+9]) cube([8,7,8]);
}

module cable_guide(x,y,len=100) {
    difference() {
        translate([x,y,floor_t+1]) cube([len,8,9]);
        translate([x+2,y+2,floor_t]) cube([len-4,4,10]);
    }
}

module lid() {
    difference() {
        rounded_box(L,W,4,corner_r);
        for (x=[20:20:L-20], y=[20:20:W-20])
            translate([x,y,-1]) cylinder(h=6,d=3);
        for (x=[20:12:L-20])
            translate([x,W/2-22,-1]) cube([5,44,6]);
    }
}

tray();
if (show_modules) {
    generic_compute_node(18,18);
    generic_compute_node(18,98);
    power_distribution(132,18);
    network_switch(132,76);
}
if (show_cable_guides) {
    cable_guide(118,22,10);
    cable_guide(118,105,10);
    cable_guide(18,84,92);
}
if (show_lid) translate([0,0,H+8]) color([0.42,0.45,0.5,0.6]) lid();
