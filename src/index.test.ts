/**
 * Tests for tts-sidecar TypeScript wrapper
 */

import { TtsSidecar, TtsOptions } from './index';

// Simple mock factory to avoid type issues
const createMockProc = () => ({
  on: jest.fn().mockReturnThis(),
  stdout: { on: jest.fn().mockReturnThis() },
  stderr: { on: jest.fn().mockReturnThis() },
});

// Mock child_process module
jest.mock('child_process', () => ({
  spawn: jest.fn(),
}));

// Mock fs module
jest.mock('fs', () => ({
  promises: {
    mkdir: jest.fn().mockResolvedValue(undefined),
  },
}));

import { spawn } from 'child_process';

const mockSpawn = spawn as jest.MockedFunction<typeof spawn>;

describe('TtsSidecar', () => {
  let tts: TtsSidecar;

  beforeEach(() => {
    jest.clearAllMocks();
    tts = new TtsSidecar('/path/to/tts-sidecar');
  });

  describe('constructor', () => {
    it('should create instance with custom binary path', () => {
      const ttsCustom = new TtsSidecar('/custom/path');
      expect(ttsCustom).toBeInstanceOf(TtsSidecar);
    });

    it('should create instance with default binary path', () => {
      const ttsDefault = new TtsSidecar();
      expect(ttsDefault).toBeInstanceOf(TtsSidecar);
    });
  });

  describe('version', () => {
    it('should parse version from output', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      // Simulate stdout data
      (mockProc.stdout.on as jest.Mock).mockImplementation((event: string, cb: (data: Buffer) => void) => {
        if (event === 'data') {
          cb(Buffer.from('tts-sidecar v0.1.0\nMotor TTS'));
        }
        return mockProc.stdout;
      });

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      const version = await tts.version();
      expect(version).toBe('0.1.0');
      expect(mockSpawn).toHaveBeenCalledWith(
        '/path/to/tts-sidecar',
        ['version'],
        expect.any(Object)
      );
    });
  });

  describe('voices', () => {
    it('should parse voices from output', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.stdout.on as jest.Mock).mockImplementation((event: string, cb: (data: Buffer) => void) => {
        if (event === 'data') {
          cb(Buffer.from(`=== Voces disponibles ===

ID                   Nombre                              Idioma
-----------------------------------------------------------------
af_sarah             Sarah (American Female)             en-US

Total: 1 voces`));
        }
        return mockProc.stdout;
      });

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      const voices = await tts.voices();
      expect(voices.length).toBeGreaterThan(0);
      expect(voices[0]).toHaveProperty('id');
      expect(voices[0]).toHaveProperty('name');
      expect(voices[0]).toHaveProperty('language');
    });
  });

  describe('devices', () => {
    it('should parse devices from output', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.stdout.on as jest.Mock).mockImplementation((event: string, cb: (data: Buffer) => void) => {
        if (event === 'data') {
          cb(Buffer.from(`=== Dispositivos de audio ===

Índice     Nombre                                   Predeterminado
------------------------------------------------------------
0          Speakers                                 Sí`));
        }
        return mockProc.stdout;
      });

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      const devices = await tts.devices();
      expect(devices.length).toBeGreaterThan(0);
      expect(devices[0]).toHaveProperty('index');
      expect(devices[0]).toHaveProperty('name');
      expect(devices[0]).toHaveProperty('is_default');
    });
  });

  describe('speak', () => {
    it('should call speak with text', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      await tts.speak('Hello world');

      expect(mockSpawn).toHaveBeenCalledWith(
        '/path/to/tts-sidecar',
        ['speak', '--text', 'Hello world'],
        expect.any(Object)
      );
    });

    it('should include options when provided', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      const options: TtsOptions = { voice: 'af_sarah', speed: 1.2, volume: 0.8 };
      await tts.speak('Hello', options);

      expect(mockSpawn).toHaveBeenCalledWith(
        '/path/to/tts-sidecar',
        ['speak', '--text', 'Hello', '--voice', 'af_sarah', '--speed', '1.2', '--volume', '0.8'],
        expect.any(Object)
      );
    });

    it('should throw error for empty text', async () => {
      await expect(tts.speak('')).rejects.toThrow('Text cannot be empty');
      await expect(tts.speak('   ')).rejects.toThrow('Text cannot be empty');
    });
  });

  describe('synthesize', () => {
    it('should call synthesize with text and output', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      await tts.synthesize('Hello', '/output.wav');

      expect(mockSpawn).toHaveBeenCalledWith(
        '/path/to/tts-sidecar',
        ['synthesize', '--text', 'Hello', '--output', '/output.wav'],
        expect.any(Object)
      );
    });

    it('should include voice option when provided', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          setTimeout(() => cb(0), 0);
        }
        return mockProc;
      });

      await tts.synthesize('Hello', '/output.wav', { voice: 'bm_david' });

      expect(mockSpawn).toHaveBeenCalledWith(
        '/path/to/tts-sidecar',
        ['synthesize', '--text', 'Hello', '--output', '/output.wav', '--voice', 'bm_david'],
        expect.any(Object)
      );
    });

    it('should throw error for empty text', async () => {
      await expect(tts.synthesize('', '/output.wav')).rejects.toThrow('Text cannot be empty');
    });

    it('should throw error for empty output path', async () => {
      await expect(tts.synthesize('Hello', '')).rejects.toThrow('Output path cannot be empty');
    });
  });

  describe('error handling', () => {
    it('should throw TtsSidecarError on non-zero exit', async () => {
      const mockProc = createMockProc();
      mockSpawn.mockReturnValue(mockProc as any);

      (mockProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
        if (event === 'close') {
          cb(1);
        }
        return mockProc;
      });

      (mockProc.stderr.on as jest.Mock).mockImplementation((event: string, cb: (data: Buffer) => void) => {
        if (event === 'data') {
          cb(Buffer.from('Error message'));
        }
        return mockProc.stderr;
      });

      await expect(tts.version()).rejects.toThrow();
    });

    it('should throw TtsSidecarError on spawn error', async () => {
      mockSpawn.mockImplementation(() => {
        const errorProc = createMockProc();
        (errorProc.on as jest.Mock).mockImplementation((event: string, cb: (...args: any[]) => void) => {
          if (event === 'error') {
            cb(new Error('ENOENT'));
          }
          return errorProc;
        });
        return errorProc as any;
      });

      await expect(tts.version()).rejects.toThrow();
    });
  });
});
