import { filenameFor } from './receipts';

describe('filenameFor', () => {
  it('mantém o nome original quando ele já tem extensão de imagem', () => {
    expect(filenameFor('file:///data/user/0/cache/IMG_0042.jpg', 'image/jpeg')).toBe(
      'IMG_0042.jpg',
    );
    expect(filenameFor('file:///tmp/foto.PNG', 'image/png')).toBe('foto.PNG');
  });

  it('inventa um nome com extensão quando a URI não tem', () => {
    // Sem extensão o backend não infere o mimetype e o Mindee recusa o arquivo.
    expect(filenameFor('file:///tmp/ABCD-1234', 'image/jpeg')).toBe('recibo.jpg');
    expect(filenameFor('file:///tmp/ABCD-1234', 'image/png')).toBe('recibo.png');
    expect(filenameFor('file:///tmp/ABCD-1234', 'image/heic')).toBe('recibo.heic');
  });

  it('ignora query string na URI', () => {
    expect(filenameFor('content://media/foto.jpg?width=100', 'image/jpeg')).toBe('foto.jpg');
  });

  it('cai no jpg quando o mimetype vem estranho', () => {
    expect(filenameFor('file:///tmp/sem-nome', 'coisa-esquisita')).toBe('recibo.jpg');
  });
});
