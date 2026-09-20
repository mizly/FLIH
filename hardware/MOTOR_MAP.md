# FLIH motor map

The values that make W/A/S/D do what they say. Without them the robot drives
backwards, because nothing in the wiring tells the software which end is the front.

```sh
ROBOT_MOTOR_SIGNS=1,-1,-1,1
ROBOT_MOTOR_SIDES=L,R,L,R
```

Both were confirmed on the hardware: all four wheels forward on W, backward on S,
the cart rotating left on A and right on D.

## The harness

| Board output | Wheel, as labelled on the chassis | Drives side |
| ------------ | --------------------------------- | ----------- |
| M1           | back right                        | L           |
| M2           | back left                         | R           |
| M3           | front right                       | L           |
| M4           | front left                        | R           |

The side column looks wrong against the labels, and that is the point: **the end
labelled "front" is not the end the robot drives toward.** Rotation seen from above
is the same whichever end you call the front, but forward is not, which is why the
turns were correct while forward and reverse were inverted. Flipping every sign
would have fixed forward and broken the turns; flipping the signs *and* the sides
negates forward alone, which is what these values do.

Relabel the chassis and this table gets simpler. Until someone does, trust the
env vars over the sticker.

## What each variable does

`ROBOT_MOTOR_SIGNS` is per-motor polarity, M1 to M4, and only compensates for how a
motor's two leads happen to be soldered. Get one wrong and that single wheel fights
the other three.

`ROBOT_MOTOR_SIDES` says which side of the robot each output drives, so `drive()`
knows what to mix. Get it wrong and driving straight still looks perfect - every
wheel turns the same way - while turning does something arbitrary. That is what
makes it worth writing down: a wrong side map is invisible until you turn.

## Re-deriving it

With the chassis propped and all four wheels off the ground:

```sh
python backend/motor_check.py
```

It drives each motor alone, then the four teleop motions, announcing what each step
should look like. Any wheel that turns backward on its own step gets its slot in
`ROBOT_MOTOR_SIGNS` flipped. If every wheel is right but A and D rotate the wrong
way, the side map is wrong, not the signs. If forward and reverse are inverted while
the turns are correct, flip the signs and the sides together.
