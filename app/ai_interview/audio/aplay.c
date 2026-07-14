/*
* Copyright (c) 2019-2025 Allwinner Technology Co., Ltd. ALL rights reserved.
*
* Allwinner is a trademark of Allwinner Technology Co.,Ltd., registered in
* the the people's Republic of China and other countries.
* All Allwinner Technology Co.,Ltd. trademarks are used with permission.
*
* DISCLAIMER
* THIRD PARTY LICENCES MAY BE REQUIRED TO IMPLEMENT THE SOLUTION/PRODUCT.
* IF YOU NEED TO INTEGRATE THIRD PARTY’S TECHNOLOGY (SONY, DTS, DOLBY, AVS OR MPEGLA, ETC.)
* IN ALLWINNERS’SDK OR PRODUCTS, YOU SHALL BE SOLELY RESPONSIBLE TO OBTAIN
* ALL APPROPRIATELY REQUIRED THIRD PARTY LICENCES.
* ALLWINNER SHALL HAVE NO WARRANTY, INDEMNITY OR OTHER OBLIGATIONS WITH RESPECT TO MATTERS
* COVERED UNDER ANY REQUIRED THIRD PARTY LICENSE.
* YOU ARE SOLELY RESPONSIBLE FOR YOUR USAGE OF THIRD PARTY’S TECHNOLOGY.
*
*
* THIS SOFTWARE IS PROVIDED BY ALLWINNER"AS IS" AND TO THE MAXIMUM EXTENT
* PERMITTED BY LAW, ALLWINNER EXPRESSLY DISCLAIMS ALL WARRANTIES OF ANY KIND,
* WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING WITHOUT LIMITATION REGARDING
* THE TITLE, NON-INFRINGEMENT, ACCURACY, CONDITION, COMPLETENESS, PERFORMANCE
* OR MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
* IN NO EVENT SHALL ALLWINNER BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
* SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
* NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS, OR BUSINESS INTERRUPTION)
* HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
* STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
* ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
* OF THE POSSIBILITY OF SUCH DAMAGE.
*/
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <math.h>
#include <hal_cmd.h>
#include <aw-alsa-lib/pcm.h>
#include <hal_time.h>
#include <hal_timer.h>
#include <opus.h>
#include "common.h"
#include "wav_parser.h"
#include <ipc_udp.h>
#include <cfg.h>

static p_ipc_endpoint_t g_ipc_ep_audio_download;
static unsigned int g_playback_time = 0;
static unsigned int g_playback_loop_enable = 0;
static unsigned int g_playback_mode = 0;
static char *g_pcm_name;
static char *g_hpcm_name;
extern unsigned int g_verbose;

static int decode_then_play(audio_mgr_t *mgr)
{
#define MAX_PACKET_SIZE 4000
	int ret = 0;
	unsigned int frame_bytes = 0;
	ssize_t r = 0;
	char *audiobuf = NULL;
	unsigned char *opusbuf = NULL;
	int opuslen;
	int opened = 0;

	audiobuf = malloc(40960);
	opusbuf = malloc(MAX_PACKET_SIZE);
	if (!audiobuf || !opusbuf) { goto err_malloc; }

	OpusDecoder *dec = opus_decoder_create(24000, 1, &ret);

	while (1)
	{
		while (0 != g_ipc_ep_audio_download->recv(g_ipc_ep_audio_download,
		       opusbuf, MAX_PACKET_SIZE, &opuslen));

		if (!opened) {
			ret = snd_vela_pcm_open(&mgr->handle, g_pcm_name,
			       SND_VELA_PCM_STREAM_PLAYBACK, 0);
			if (ret < 0) { usleep(100000); continue; }
			mgr->period_size = 1024;
			mgr->buffer_size = 16384;
			set_param(mgr->handle, mgr->format, mgr->rate,
				  mgr->channels, mgr->period_size, mgr->buffer_size);
			frame_bytes = snd_vela_pcm_frames_to_bytes(mgr->handle, 1);
			opened = 1;
		}

		int output_samples = opus_decode(dec, opusbuf, opuslen,
		       (opus_int16 *)audiobuf, 2880, 0);
		if (output_samples < 0) continue;

		/* 升采样：24000Hz 1ch → 48000Hz 2ch（线性插值改善音质） */
		if (output_samples > 0) {
			opus_int16 *tmp = malloc(output_samples * sizeof(opus_int16));
			memcpy(tmp, audiobuf, output_samples * sizeof(opus_int16));
			
			/* 升采样：24000Hz 1ch → 48000Hz 2ch */
			for (int i = output_samples - 1; i >= 0; i--) {
    			opus_int16 s = ((opus_int16 *)audiobuf)[i];
    			((opus_int16 *)audiobuf)[i*4] = s;
    			((opus_int16 *)audiobuf)[i*4+1] = s;
    			((opus_int16 *)audiobuf)[i*4+2] = s;
    			((opus_int16 *)audiobuf)[i*4+3] = s;
		}
		output_samples *= 4;

		}

		r = pcm_write(mgr->handle, audiobuf, output_samples, frame_bytes);
		if (r != output_samples) {
			snd_vela_pcm_prepare(mgr->handle);
			pcm_write(mgr->handle, audiobuf, output_samples, frame_bytes);
		}
	}

	opus_decoder_destroy(dec);
err_malloc:
	free(audiobuf);
	free(opusbuf);
	return -1;
}





/*
 * arg0: aplay
 * arg1: card
 * arg2: format
 * arg3: rate
 * arg4: channels
 * arg5: data
 * arg6: len
 */
int aplay(const char *card_name, snd_pcm_format_t format, unsigned int rate,
			unsigned int channels, const char *data, unsigned int datalen)
{
	int ret = 0;
	snd_pcm_t *handle;
	int mode = 0;
	snd_pcm_uframes_t period_frames = 1024, buffer_frames = 4096;

	syslog(LOG_INFO,"dump args:\n");
	syslog(LOG_INFO,"card:	     %s\n", card_name);
	syslog(LOG_INFO,"format:      %u\n", format);
	syslog(LOG_INFO,"rate:	     %u\n", rate);
	syslog(LOG_INFO,"channels:    %u\n", channels);
	syslog(LOG_INFO,"data:	     %p\n", data);
	syslog(LOG_INFO,"datalen:     %u\n", datalen);
	syslog(LOG_INFO,"period_size: %lu\n", period_frames);
	syslog(LOG_INFO,"buffer_size: %lu\n", buffer_frames);

	/* open card */
	ret = snd_vela_pcm_open(&handle, card_name, SND_VELA_PCM_STREAM_PLAYBACK, mode);
	if (ret < 0) {
		syslog(LOG_ERR,"audio open error:%d\n", ret);
		return -1;
	}

	ret = set_param(handle, format, rate, channels, period_frames, buffer_frames);
	if (ret < 0)
		goto err1;

	ret = pcm_write(handle, (char *)data,
			snd_vela_pcm_bytes_to_frames(handle, datalen),
			snd_vela_pcm_frames_to_bytes(handle, 1));
	if (ret < 0) {
		syslog(LOG_ERR,"pcm_write error:%d\n", ret);
		goto err1;
	}

	ret = snd_vela_pcm_drain(handle);
	/*ret = snd_vela_pcm_drop(handle);*/
	if (ret < 0)
		syslog(LOG_ERR,"stop failed!, return %d\n", ret);
err1:
	/* close card */
	ret = snd_vela_pcm_close(handle);
	if (ret < 0) {
		syslog(LOG_ERR,"audio close error:%d\n", ret);
		return ret;
	}
	return 0;
}

static int play_fs_music(audio_mgr_t *mgr, const char *path)
{
	int ret = 0, fd = 0;
	wav_header_t wav_header;
	wav_hw_params_t wav_hwparams = {16000, SND_PCM_FORMAT_UNKNOWN, 2};
	unsigned int c, written = 0, count = UINT_MAX;
	unsigned int chunk_bytes, frame_bytes = 0;
	ssize_t r = 0;
	audio_mgr_t *audio_hpcm_mgr = NULL;
	char *audiobuf = NULL;

	fd = open(path, O_RDONLY);
	if (fd < 0) {
		syslog(LOG_INFO,"no such wav file\n");
		return -1;
	}
	/* mode 0:wav 1:pcm */
	if (g_playback_mode == 0) {
		r = read(fd, &wav_header, sizeof(wav_header_t));
		if (r != sizeof(wav_header_t)) {
			syslog(LOG_ERR,"read wav file header failed, return %ld\n",(long int)r);
			goto err_fread_wav_header;
		}


		if (check_wav_header(&wav_header, &wav_hwparams) != 0) {
			syslog(LOG_ERR,"check wav header failed\n");
			goto err_check_wav_header;
		}
	}

	/* open card */
	ret = snd_vela_pcm_open(&mgr->handle, g_pcm_name, SND_VELA_PCM_STREAM_PLAYBACK, 0);
	if (ret < 0) {
		syslog(LOG_ERR,"audio open error:%d\n", ret);
		goto err_pcm_open_pcm;
	}

	if (g_playback_mode == 0) {
		mgr->format = wav_hwparams.format;
		mgr->rate = wav_hwparams.rate;
		mgr->channels = wav_hwparams.channels;
	}
	syslog(LOG_INFO,"dump args:\n");
	syslog(LOG_INFO,"card:	     %s\n", g_pcm_name);
	syslog(LOG_INFO,"format:      %u\n", mgr->format);
	syslog(LOG_INFO,"rate:	     %u\n", mgr->rate);
	syslog(LOG_INFO,"channels:    %u\n", mgr->channels);
	syslog(LOG_INFO,"period_size: %lu\n", mgr->period_size);
	syslog(LOG_INFO,"buffer_size: %lu\n", mgr->buffer_size);

	ret = set_param(mgr->handle, mgr->format, mgr->rate, mgr->channels,
			mgr->period_size, mgr->buffer_size);
	if (ret < 0) {
		syslog(LOG_ERR,"audio set pcm param error:%d\n", ret);
		goto err_set_param_pcm;
	}

	if (g_hpcm_name) {
		audio_hpcm_mgr = audio_mgr_create();
		if (!audio_hpcm_mgr) {
			syslog(LOG_ERR,"audio hpcm create manager failed.\n");
			goto err_hpcm_create_mgr;
		}
		/* open card */
		ret = snd_vela_pcm_open(&audio_hpcm_mgr->handle, g_hpcm_name,
			SND_VELA_PCM_STREAM_PLAYBACK, 0);
		if (ret < 0) {
			syslog(LOG_ERR,"audio open error:%d\n", ret);
			goto err_pcm_open_hpcm;
		}
		audio_hpcm_mgr->format = wav_hwparams.format;
		audio_hpcm_mgr->rate = wav_hwparams.rate;
		audio_hpcm_mgr->channels = wav_hwparams.channels;
		audio_hpcm_mgr->period_size = mgr->period_size;
		audio_hpcm_mgr->buffer_size = mgr->buffer_size;

		ret = set_param(audio_hpcm_mgr->handle,
				audio_hpcm_mgr->format,
				audio_hpcm_mgr->rate,
				audio_hpcm_mgr->channels,
				audio_hpcm_mgr->period_size,
				audio_hpcm_mgr->buffer_size);
		if (ret < 0) {
			syslog(LOG_ERR,"audio set pcm param error:%d\n", ret);
			goto err_set_param_hpcm;
		}
	}
	if (g_playback_mode == 0) {
		count = wav_header.dataSize;
	}
	frame_bytes = snd_vela_pcm_frames_to_bytes(mgr->handle, 1);
	chunk_bytes = snd_vela_pcm_frames_to_bytes(mgr->handle, mgr->period_size);

	audiobuf = malloc(chunk_bytes);
	if (!audiobuf) {
		syslog(LOG_ERR,"no memory...\n");
		goto err_malloc_audiobuf;
	}
	while (written < count) {
		c = count - written;
		if (c > chunk_bytes)
			c = chunk_bytes;
		r = read(fd, audiobuf, c);
		if (r < 0 || r != c) {
			syslog(LOG_ERR,"read file error, r=%ld,c=%u\n", (long int)r, c);
			break;
		}
		r = pcm_write(mgr->handle, audiobuf, r/frame_bytes, frame_bytes);
		if (r != c/frame_bytes)
			break;
		written += c;
	}
	snd_vela_pcm_drain(mgr->handle);

	free(audiobuf);
	/* close card */
	if (mgr->handle != NULL)
		snd_vela_pcm_close(mgr->handle);
	if (audio_hpcm_mgr) {
		if (audio_hpcm_mgr->handle != NULL) {
			snd_vela_pcm_close(audio_hpcm_mgr->handle);
		}
		audio_mgr_release(audio_hpcm_mgr);
		g_hpcm_name = NULL;
	}
	close(fd);
	return 0;

err_malloc_audiobuf:
err_set_param_hpcm:
	if (audio_hpcm_mgr && (audio_hpcm_mgr->handle != NULL))
		snd_vela_pcm_close(audio_hpcm_mgr->handle);
err_pcm_open_hpcm:
	if (g_hpcm_name) {
		audio_mgr_release(audio_hpcm_mgr);
		g_hpcm_name = NULL;
	}
err_hpcm_create_mgr:
err_set_param_pcm:
	/* close card */
	if (mgr->handle != NULL)
		snd_vela_pcm_close(mgr->handle);
err_pcm_open_pcm:
err_check_wav_header:
err_fread_wav_header:
	close(fd);
	return ret;
}

#define PI (3.1415926)
static int sine_generate(void **buf, uint32_t *len, uint32_t rate, uint32_t channels, uint8_t bits)
{
	int16_t *data_16;
	int32_t *data_32;
	int sine_hz = 1000;
	int sine_point;
	int accuracy;
	int i, j;

	sine_point = rate / sine_hz;

	if (bits == 16) {
		data_16 = malloc(sine_point * sizeof(int16_t) * channels);
		if(!data_16){
                   return -1;
		}
		accuracy = INT16_MAX;
		for (i = 0; i < sine_point; i++) {
			int16_t value = (int16_t)(accuracy * sin(2 * (double)PI * i / sine_point));
			for (j = 0; j < channels; j++)
				data_16[(i * channels) + j] = value;
		}

		*buf = data_16;
		*len = sine_point * sizeof(int16_t) * channels;
	} else if (bits == 32) {
		data_32 = malloc(sine_point * sizeof(int32_t) * channels);
		if(!data_32)
		{
                   return -1;
		}
		accuracy = INT32_MAX;
		for (i = 0; i < sine_point; i++) {
			int32_t value = (int32_t)(accuracy * sin(2 * (double)PI * i / sine_point));
			for (j = 0; j < channels; j++)
				data_32[(i * channels) + j] = value;
		}

		*buf = data_32;
		*len = sine_point * sizeof(int32_t) * channels;
	} else {
		*buf = NULL;
		*len = 0;
		syslog(LOG_ERR,"unsupport bits:%u\n", bits);
		return -1;
	}

	return 0;
}

static int play_fs_sine(audio_mgr_t *mgr)
{
	int ret;
	unsigned int total_frames = 0;
	unsigned int stop_frames = 0;
	int frame_write;
	int frame_size;
	void *sine_buf = NULL;
	uint32_t sine_buf_len = 0;

	ret = snd_vela_pcm_open(&mgr->handle, g_pcm_name, SND_VELA_PCM_STREAM_PLAYBACK, 0);
	if (ret < 0) {
		syslog(LOG_ERR,"audio open error:%d\n", ret);
		goto err_pcm_open_pcm;
	}

	ret = set_param(mgr->handle, mgr->format, mgr->rate, mgr->channels,
			mgr->period_size, mgr->buffer_size);
	if (ret < 0) {
		syslog(LOG_ERR,"audio set pcm param error:%d\n", ret);
		goto err_set_param_pcm;
	}

	ret = sine_generate(&sine_buf, &sine_buf_len, mgr->rate, mgr->channels, mgr->format_bits);
	if (ret < 0) {
		syslog(LOG_ERR,"sine_generate failed\n");
		goto err_sine_generate;
	}

	frame_size = snd_vela_pcm_frames_to_bytes(mgr->handle, 1);
	frame_write = snd_vela_pcm_bytes_to_frames(mgr->handle, sine_buf_len);
	stop_frames = mgr->rate * g_playback_time;
	while (1) {
		ret = pcm_write(mgr->handle, sine_buf, frame_write, frame_size);
		if (ret < 0) {
			syslog(LOG_ERR,"pcm_write error:%d\n", ret);
			break;
		}
		total_frames += frame_write;
		if (total_frames >= stop_frames)
			break;
	}
	snd_vela_pcm_drain(mgr->handle);
	if (mgr->handle != NULL)
		snd_vela_pcm_close(mgr->handle);
	if (sine_buf)
		free(sine_buf);

	return 0;

err_sine_generate:
err_set_param_pcm:
	if (mgr->handle != NULL)
		snd_vela_pcm_close(mgr->handle);
err_pcm_open_pcm:
	return ret;
}

static void usage(void)
{
	syslog(LOG_INFO,"Usage: aplay [option] wav_file\n");
	syslog(LOG_INFO,"    -D,        pcm device name\n");
	syslog(LOG_INFO,"    -H,        Hub pcm device name\n");
	syslog(LOG_INFO,"    -p,        period size\n");
	syslog(LOG_INFO,"    -b,        buffer size\n");
	syslog(LOG_INFO,"    -l,        loop play builtin music mode\n");
	syslog(LOG_INFO,"    -s,        play sine wave mode\n");
	syslog(LOG_INFO,"    -t,        play sine wave time\n");
	syslog(LOG_INFO,"    -v,        show pcm setup\n");
	syslog(LOG_INFO,"    -o,        decode by opus\n"); /* 100ask */
	syslog(LOG_INFO,"    -h,        show usage\n");
	syslog(LOG_INFO,"\n");
}
#ifdef CONFIG_KERNEL_FREERTOS
int cmd_aplay(int argc, char **argv)
#elif defined(CONFIG_OS_NUTTX)
int main(int argc, char **argv)
#endif
{
	int play_sine = 0;
	audio_mgr_t *audio_mgr = NULL;
	char *file_path = NULL;
	g_hpcm_name = NULL;
	g_pcm_name = "default";
	g_verbose = 0;
	g_playback_mode = 0;

	int use_opus = 0;

	if (argc < 2) {
		usage();
		return 0;
	}

	audio_mgr = audio_mgr_create();
	if (!audio_mgr) {
		syslog(LOG_ERR,"audio_mgr_create failed\n");
		return -1;
	}

	argv += 1;
	while (*argv) {
		if (strcmp(*argv, "-D") == 0) {
			argv++;
			if (*argv)
				g_pcm_name = *argv;
		} else if (strcmp(*argv, "-H") == 0) {
			argv++;
			if (*argv)
				g_hpcm_name = *argv;
		} else if (strcmp(*argv, "-p") == 0) {
			argv++;
			if (*argv)
				audio_mgr->period_size = atoi(*argv);
		} else if (strcmp(*argv, "-b") == 0) {
			argv++;
			if (*argv)
				audio_mgr->buffer_size = atoi(*argv);
		} else if (strcmp(*argv, "-c") == 0) {
			argv++;
			if (*argv)
				audio_mgr->channels = atoi(*argv);
		} else if (strcmp(*argv, "-r") == 0) {
			argv++;
			if (*argv)
				audio_mgr->rate = atoi(*argv);
		} else if (strcmp(*argv, "-f") == 0) {
			argv++;
			if (*argv) {
				audio_mgr->format_bits = atoi(*argv);
				switch (audio_mgr->format_bits) {
				case 16:
					audio_mgr->format = SND_PCM_FORMAT_S16_LE;
					break;
				case 24:
					audio_mgr->format = SND_PCM_FORMAT_S24_LE;
					break;
				case 32:
					audio_mgr->format = SND_PCM_FORMAT_S32_LE;
					break;
				default:
					syslog(LOG_ERR,"%u bits not supprot\n", audio_mgr->format_bits);
				return -1;
				}
			}
		} else if (strcmp(*argv, "-s") == 0) {
			play_sine = 1;
		} else if (strcmp(*argv, "-t") == 0) {
			argv++;
			if (*argv)
				g_playback_time = atoi(*argv);
		} else if (strcmp(*argv, "-m") == 0) {
			argv++;
			if (*argv)
				g_playback_mode = atoi(*argv);
		} else if (strcmp(*argv, "-l") == 0) {
			g_playback_loop_enable = 1;
		} else if (strcmp(*argv, "-o") == 0) {
			use_opus = 1;
		} else if (strcmp(*argv, "-v") == 0) {
			g_verbose = 1;
		} else if (strcmp(*argv, "-h") == 0) {
			usage();
			goto err;
		} else {
			file_path = *argv;
		}

		if (*argv)
			argv++;
	}

	if (use_opus) {
		g_ipc_ep_audio_download = ipc_endpoint_create_udp(AUDIO_PORT_DOWN, 0, NULL, NULL);
		if (!g_ipc_ep_audio_download) {
			fprintf(stderr, "Failed to create IPC endpoint\n");
			return -1;
		}
				
		decode_then_play(audio_mgr);
	} else if (play_sine) {
		play_fs_sine(audio_mgr);
	} else {
		play_fs_music(audio_mgr, file_path);
	}

err:
	audio_mgr_release(audio_mgr);
	return 0;
}
#ifdef CONFIG_KERNEL_FREERTOS
FINSH_FUNCTION_EXPORT_CMD(cmd_aplay, aplay, Play music);
#endif
