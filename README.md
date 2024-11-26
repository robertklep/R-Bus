# R-Bus

Virtually every modern heater and thermostat will speak OpenTherm, but Remeha in their infinite wisdom created their own protocol called R-Bus. This protocol is to the best of my knowledge completely undocumented, so this is my attempt at doing that.

## Current status

### Nov 25, 2024

I am trying to find the temperature in the data somewhere.
I've tried to parse every right-alligned number type that fits in a payload, and the most promising candidates
seem to be the numbers in the 20k range I saw last time, but they don't exactly match the temperature.

Could they be the water temperature?
You might expect hot water to be around 50&deg;C and the return temperature of the water to be slightly above ambient.
Sadly I can't see those temperatures in the app to verify.

Working on the assumption that in cases where the first 3 bytes of the request and reply payload match they indicate some register,
I wrote a script that groups messages by type and register to see how they change over time.
Many of them are constant and uninteresting, and som vary seemingly at random.
But some vary at a few distinct points in time, possibly in response to me messing with the settings.

I've collected these messages in [registers.txt](registers.txt).
For now they don't make much sense yet but it narrows down the search space.
It also clearly shows that there are some bit errors that could explain some weirdness.

I've also had the idea to look for ascii data in the payloads.
That wont get us the temperature, but it might give some other insights.
I've collected these messages in [ascii.txt](ascii.txt).
You can see fun stuff like `Zone1` for the heating zone, `EHC-07` the model of the heat pump, `7733242-06` and `7711844-06` could be serial numbers, and `MK2.1` could be a hardware revision, there are also heating modes like `Home` and `Sleep`. Other than that I'm not sure what we can learn here.

One thing it does seem to confirm is that the replies are coming from `EHC-07`, the heat pump,
which suggests the requests are from the thermostat.

This also suggests that we should look for the thermostat set points in the requests.

### Nov 22, 2024

I have started poking around with the message type.
I'm operating under the assumption that the first unknown byte is some kind of message type.
A particular interaction caught my eye where a `FA` request was answered with an `F3` reply.
In all `FA` requests there is a 5 byte payload that seems to be roughly

| byte | meaning |
|---|---|
|`20 02 01` | address?|
| `73 F0` | unknown |

and a `F3` reply of the form

| byte | meaning |
|---|---|
|`20 02 01` | same address |
| `00 00 00 00 00 00 6C 4A` | uint_64? |

I counted the reply bytes and their length and there seem to be 4 very common `Fx` replies with a common length. Most but not all follow the 3 byte "address" pattern.

```
Counter({'F7 7': 984,
         'F5 9': 802,
         'F8 6': 740,
         'F3 11': 715,
         'E6 24': 41,
         'FE 1': 17,
         'FA 5': 17,
         'E5 25': 14,
         'EF 15': 9,
         '00 0': 5,
         '2E 1': 3,
         '2D 1': 1,
         'F5 25': 1,
         '7D 9': 1,
         '2E 9': 1,
         '01 100': 1,
         'F9 5': 1,
         'F3 43': 1,
         '00 1': 1,
         '0A 1': 1,
         'A4 187': 1})
```

I tried parsing those supposed uint_64 with the following result. I was hoping it'd be something obvious like the temperature in millidegrees but while not miles off, not exactly. (recall it was 20&deg;C at the time)

```
(48, 35, 0, 12151716762370106083)
(32, 2, 1, 16762457204505351945)
(52, 33, 1, 25079)
(32, 2, 1, 16762457204505351945)
(32, 2, 1, 27722)
(48, 35, 0, 13315615791068642237)
(32, 2, 1, 16762457204505351945)
(32, 2, 1, 27722)
(52, 35, 1, 47222)
(52, 34, 1, 29879)
(52, 33, 1, 25079)
(32, 2, 1, 16762457204505351945)
(32, 2, 1, 27722)
(48, 35, 0, 10876635117870837854)
(32, 2, 1, 27722)
(52, 35, 1, 47222)
(52, 34, 1, 29879)
(52, 33, 1, 25079)
(48, 35, 0, 3173792004718625437)
(32, 2, 1, 16762457204505351945)
(32, 2, 1, 27722)
```

One thing that is slightly concerning is that there are some parse errors after really long messages. Not sure if just a glitch in the serial data, or something funky like replacing certain bytes. I remember Pokemon has a whole thing where they replace 0xFE with something else and then send a whole mask array, because 0xFE is their handshake byte.

### Nov 8, 2024

I have started building a parser that breaks a stream of bytes from the logger into messages.
Turns out I was decoding the bit order wrong, and now some things are more obvious.
The format seems to be


| byte | meaning |
|---|---|
|`01 00`| header |
| `01` | request/reply |
| `00` | some bit flags? |
| `07` | payload length |
| `F7 01 FE` | unknown |
| `10 03 01 FF FF 85 9C` | payload |

### Nov 6, 2024

I have built a data logger with a comparator and an Arduino, and collected a good long chunk of messages in [log.txt](log.txt),
while simultaneously collecting screenshots of the official app in [screenshots](screenshots) and adjusting the temperature between 20&deg;C and 22&deg;C.

The schematic of the datalogger is in [demodulator.pdf](demodulator.pdf), and the Arduino sketch is in [echo.ino](echo/echo.ino).

Analysis of the new data tbd.

### Oct 14, 2024

I have collected an oscilloscope capture of the wires between my [Remeha Elga Ace](https://www.remeha.nl/product/elga-ace) heat pump and [Remeha eTwist](https://www.remeha.nl/product/etwist) thermostat. This can be found as a compressed CSV file in `RigolDS1.tar.xz`.

It appears to be a simple on-off keying scheme with a 500kHz carrier and a 10kHz bit rate.

To decode the capture, I first demodulate it with `demodulate.py`, and then import `demodulated_output.csv` in [urh](https://github.com/jopohl/urh). Automated detection worked correctly, but I did set the pause threshold and message length divisor to 10. The analysis tab proved unhelpful so I just exported the data to `protocol.proto.xml`.

My hunch is that it's regular old 8N1 UART data, but possibly inverted. In `decode_bytes.py` I read the exported XML from urh, verify start and stop bits, and extract the data bits. The output is stored in `messages.txt`, a sample is provided below:

```
80 00 00 00 A0 5F 00 80 2C C4 80 F9 95
80 00 80 00 D0 CF 80 7F 2C C4 80 00 00 00 00 00 00 1D 6E
80 00 00 00 A0 5F 00 80 2C 44 80 F0 15
80 00 80 00 D0 CF 80 7F 2C 44 80 00 00 00 00 00 00 2E ED
```

If you look at the raw capture you can see two slightly different magnitudes, so I think it is reasonable to assume this are the two devices in a request/response interaction. It seems like the first bytes are just some kind of addressing or synchronization, with the third byte being `00` in the request and `80` in the response. Possibly the fifth byte could be some message ID.

In some of the messages the last 8 bytes look like it could be an uint64 (`00 00 00 00 00 00 2E ED`), hopefully representing some useful value. The request has two bytes in that place. (`F9 95`) The three bytes before that match in the request and reply, and the byte before that is off by one. (`80 2C 44 80` -> `7F 2C 44 80`) Maybe there is some register ID or message sequence number in there?
