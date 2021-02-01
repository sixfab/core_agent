package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"
	"strings"
	"strconv"

	"github.com/creack/pty"
	"github.com/pion/webrtc"
)
var environments = `
export COLORTERM=truecolor
export LS_COLORS="rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:"
export TERM=xterm-256color
source ~/.bashrc
`

var ptmx *os.File
var terminalReady bool = false

var channels []*webrtc.DataChannel

var dc *webrtc.DataChannel

func initPtmx() error {

	// Create terminal
	c := exec.Command("bash")

	_ptmx, err := pty.Start(c)
	if err != nil {
		panic(err)
	}

	ptmx = _ptmx

	ptmx.Write([]byte(environments))

	// Make sure to close the pty at the end.
	// defer func() { _ = ptmx.Close() }() // Best effort.

	// Handle pty size.
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGWINCH)
	go func() {
		for range ch {
			if err := pty.InheritSize(os.Stdin, ptmx); err != nil {
				log.Printf("error resizing pty: %s", err)
			}
		}
	}()
	ch <- syscall.SIGWINCH // Initial resize.

	terminalReady = true
	return nil
}

func addPeer(offerText string) (answerText string) {
	fmt.Println("Adding new peer")

	// Prepare the configuration
	config := webrtc.Configuration{
		ICEServers: []webrtc.ICEServer{
			{
				URLs: []string{"stun:stun.l.google.com:19302"},
			},
		},
	}

	// Create a new RTCPeerConnection
	peerConnection, err := webrtc.NewPeerConnection(config)
	if err != nil {
		panic(err)
	}

	// Set the handler for ICE connection state
	// This will notify you when the peer has connected/disconnected
	peerConnection.OnICEConnectionStateChange(func(connectionState webrtc.ICEConnectionState) {
		fmt.Printf("ICE Connection State has changed: %s\n", connectionState.String())
	})

	// Register data channel creation handling
	peerConnection.OnDataChannel(func(d *webrtc.DataChannel) {
		fmt.Printf("New DataChannel %s %d\n", d.Label(), d.ID())

		channels = append(channels, d)

		// Register channel opening handling
		d.OnOpen(func() {
			fmt.Printf("Data channel '%s'-'%d' open. \n", d.Label(), d.ID())
		})

		// Register text message handling
		d.OnMessage(func(msg webrtc.DataChannelMessage) {
			fmt.Printf("Message from DataChannel '%s': '%s'\n", d.Label(), string(msg.Data))

			log.Println(strings.HasPrefix(string(msg.Data), "resize_"))

			if strings.HasPrefix(string(msg.Data), "resize_"){
				resize_data := strings.TrimPrefix(string(msg.Data), "resize_")
				resize_data = strings.TrimPrefix(resize_data, "resize_")
				datas := strings.Split(resize_data, ",")


				ws, err := pty.GetsizeFull(ptmx)
				if err != nil {
					log.Println(err)
					return
				}
				rows, _ := strconv.ParseUint(datas[0], 10, 16)
				cols, _ := strconv.ParseUint(datas[1], 10, 16)

				ws.Rows = uint16(rows)
				ws.Cols = uint16(cols)

				if err := pty.Setsize(ptmx, ws); err != nil {
					log.Println(err)
				}

				log.Println("Changed terminal size")

				return
			}

			if string(msg.Data) == "ping" {
				d.SendText("pong")
				return
			}

			toWrite := []byte(string(msg.Data))

			ptmx.Write(toWrite)
		})
	})

	// Wait for the offer to be pasted
	offer := webrtc.SessionDescription{}

	json.Unmarshal([]byte(offerText), &offer)

	// Set the remote SessionDescription
	err = peerConnection.SetRemoteDescription(offer)
	if err != nil {
		panic(err)
	}

	// Create an answer
	answer, err := peerConnection.CreateAnswer(nil)
	if err != nil {
		panic(err)
	}

	// Create channel that is blocked until ICE Gathering is complete
	gatherComplete := webrtc.GatheringCompletePromise(peerConnection)

	// Sets the LocalDescription, and starts our UDP listeners
	err = peerConnection.SetLocalDescription(answer)
	if err != nil {
		panic(err)
	}

	// Block until ICE Gathering is complete, disabling trickle ICE
	// we do this because we only can exchange one signaling message
	// in a production application you should exchange ICE Candidates via OnICECandidate
	<-gatherComplete

	// Output the answer in base64 so we can paste it in browser
	response, _ := json.Marshal(*peerConnection.LocalDescription())
	answerText = string(response)

	return

}

func addPeerHandler(w http.ResponseWriter, r *http.Request) {

	_reqBody, _ := ioutil.ReadAll(r.Body)

	reqBody := string(_reqBody)

	answer := addPeer(reqBody)

	fmt.Fprintf(w, answer)
}

func main() {

	initPtmx()

	fmt.Println("starting http server")
	mux := http.NewServeMux()
	mux.HandleFunc("/", addPeerHandler)

	go http.ListenAndServe(":8998", mux)

	fmt.Println("starting shell listener")
	buf := make([]byte, 1024)
	for {
		for terminalReady != true {
			time.Sleep(1 * time.Millisecond)
		}

		nr, err := ptmx.Read(buf)

		if err != nil {
			panic(err)
		}

		for _, channel := range channels {
			if err = channel.SendText(string(buf[0:nr])); err != nil {
				fmt.Println("A channel deprecated, should be removed")

				for index, _channel := range channels{
					if channel == _channel{
						channels[index] = channels[len(channels)-1]
						channels = channels[:len(channels)-1] 

						fmt.Println("removed channel")
					}
				}
			}
		}

	}

	// Block forever
	select {}
}



