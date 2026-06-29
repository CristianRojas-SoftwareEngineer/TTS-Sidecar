/**
 * tts-sidecar - TypeScript wrapper for the TTS Sidecar CLI
 *
 * Provides a typed interface to invoke the TTS sidecar binary
 * for text-to-speech synthesis and playback.
 */

import { spawn, ChildProcess, SpawnOptions } from 'child_process';
import { promises as fs } from 'fs';
import * as path from 'path';

export interface TtsOptions {
  /** Voice ID to use (e.g., 'af_sarah', 'bm_david') */
  voice?: string;
  /** Speech rate (0.5 - 2.0, default: 1.0) */
  speed?: number;
  /** Volume (0.0 - 1.0, default: 1.0) */
  volume?: number;
}

export interface Voice {
  id: string;
  name: string;
  language: string;
  gender?: string;
}

export interface AudioDevice {
  index: number;
  name: string;
  is_default: boolean;
}

export interface DoctorResult {
  modelExists: boolean;
  voicesExists: boolean;
  onnxRuntimeAvailable: boolean;
  audioAvailable: boolean;
  modelPath?: string;
  voicesPath?: string;
}

export class TtsSidecarError extends Error {
  constructor(
    message: string,
    public readonly exitCode: number | null,
    public readonly stderr?: string
  ) {
    super(message);
    this.name = 'TtsSidecarError';
  }
}

export class TtsSidecar {
  private binaryPath: string;

  /**
   * Creates a new TtsSidecar instance
   * @param binaryPath - Optional custom path to the tts-sidecar binary.
   *                     Defaults to the bin directory within the package.
   */
  constructor(binaryPath?: string) {
    if (binaryPath) {
      this.binaryPath = binaryPath;
    } else {
      // Default to the binary in the package's bin directory
      const packageRoot = path.resolve(__dirname, '..');
      const binaryName = process.platform === 'win32' ? 'tts-sidecar.exe' : 'tts-sidecar';
      this.binaryPath = path.join(packageRoot, 'bin', binaryName);
    }
  }

  /**
   * Spawns a command and returns a promise that resolves on success
   */
  private async runCommand(args: string[], options?: SpawnOptions): Promise<string> {
    return new Promise((resolve, reject) => {
      const proc: ChildProcess = spawn(this.binaryPath, args, {
        ...options,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve(stdout);
        } else {
          reject(new TtsSidecarError(
            `tts-sidecar exited with code ${code}: ${stderr || stdout}`,
            code,
            stderr
          ));
        }
      });

      proc.on('error', (err) => {
        reject(new TtsSidecarError(
          `Failed to spawn tts-sidecar: ${err.message}`,
          null,
          err.message
        ));
      });
    });
  }

  /**
   * Get the version of the tts-sidecar binary
   */
  async version(): Promise<string> {
    const output = await this.runCommand(['version']);
    // Parse "tts-sidecar v0.1.0\nMotor TTS offline..."
    const match = output.match(/tts-sidecar v(\S+)/);
    return match ? match[1] : output.trim();
  }

  /**
   * Run doctor command to check environment
   */
  async doctor(): Promise<DoctorResult> {
    const output = await this.runCommand(['doctor']);
    const result: DoctorResult = {
      modelExists: output.includes('[1/4] Verificando modelo ONNX... OK'),
      voicesExists: output.includes('[2/4] Verificando archivo de voces... OK'),
      onnxRuntimeAvailable: output.includes('[3/4] Verificando ONNX Runtime... OK'),
      audioAvailable: output.includes('[4/4] Verificando audio... OK'),
    };

    // Extract paths if present
    const modelMatch = output.match(/Ruta:\s*(\S+)/);
    if (modelMatch) result.modelPath = modelMatch[1];

    return result;
  }

  /**
   * List available voices
   */
  async voices(): Promise<Voice[]> {
    const output = await this.runCommand(['voices']);
    const voices: Voice[] = [];

    // Parse output table
    // ID                   Nombre                              Idioma
    // af_sarah             Sarah (American Female)             en-US
    const lines = output.split('\n');
    for (const line of lines) {
      // Match lines that look like voice entries (start with letter underscore)
      const match = line.match(/^(\w+)\s+(.+?)\s{2,}(\S+)\s*$/);
      if (match) {
        voices.push({
          id: match[1],
          name: match[2].trim(),
          language: match[3],
        });
      }
    }

    return voices;
  }

  /**
   * List available audio output devices
   */
  async devices(): Promise<AudioDevice[]> {
    const output = await this.runCommand(['devices']);
    const devices: AudioDevice[] = [];

    const lines = output.split('\n');
    for (const line of lines) {
      // Match device lines
      // 0          Speakers (Realtek Audio)                  Sí
      const match = line.match(/^(\d+)\s+(.+?)\s{2,}(Sí|No)\s*$/);
      if (match) {
        devices.push({
          index: parseInt(match[1], 10),
          name: match[2].trim(),
          is_default: match[3] === 'Sí',
        });
      }
    }

    return devices;
  }

  /**
   * Speak text and play audio through default device
   * @param text - Text to synthesize and speak
   * @param options - Optional synthesis options
   */
  async speak(text: string, options?: TtsOptions): Promise<void> {
    if (!text || text.trim().length === 0) {
      throw new TtsSidecarError('Text cannot be empty', null);
    }

    const args = ['speak', '--text', text];

    if (options?.voice) {
      args.push('--voice', options.voice);
    }
    if (options?.speed !== undefined) {
      args.push('--speed', String(options.speed));
    }
    if (options?.volume !== undefined) {
      args.push('--volume', String(options.volume));
    }

    await this.runCommand(args);
  }

  /**
   * Synthesize text to WAV file without playing
   * @param text - Text to synthesize
   * @param outputPath - Path to write the WAV file
   * @param options - Optional synthesis options
   */
  async synthesize(text: string, outputPath: string, options?: TtsOptions): Promise<void> {
    if (!text || text.trim().length === 0) {
      throw new TtsSidecarError('Text cannot be empty', null);
    }

    if (!outputPath || outputPath.trim().length === 0) {
      throw new TtsSidecarError('Output path cannot be empty', null);
    }

    // Ensure output directory exists
    const outputDir = path.dirname(outputPath);
    await fs.mkdir(outputDir, { recursive: true });

    const args = ['synthesize', '--text', text, '--output', outputPath];

    if (options?.voice) {
      args.push('--voice', options.voice);
    }
    if (options?.speed !== undefined) {
      args.push('--speed', String(options.speed));
    }
    if (options?.volume !== undefined) {
      args.push('--volume', String(options.volume));
    }

    await this.runCommand(args);
  }

  /**
   * Check if the binary exists and is executable
   */
  async isAvailable(): Promise<boolean> {
    try {
      await this.version();
      return true;
    } catch {
      return false;
    }
  }
}

export default TtsSidecar;
