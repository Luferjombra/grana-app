import os

OUT_DIR = "prototipo"
os.makedirs(OUT_DIR, exist_ok=True)

HEAD = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/2.44.0/iconfont/tabler-icons.min.css">
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:40px 16px; background:#2b2e33; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display:flex; justify-content:center; }
  .frame { width:390px; background:#14171c; border-radius:28px; overflow:hidden; color:#eef0f3; border:6px solid #05070a; }
</style>
</head>
<body>
<div class="frame">
"""

FOOT = """
</div>
</body>
</html>
"""

TOPBAR = """<div style="padding:1.1rem 1.1rem 0.5rem;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <p style="font-size:16px;font-weight:500;margin:0;color:#f5f6f8;">Grana</p>
    <p style="font-size:11px;color:#8a8f98;margin:2px 0 0;">Agosto · atualizado agora</p>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <button style="position:relative;width:34px;height:34px;border-radius:50%;background:#1f242c;border:none;display:flex;align-items:center;justify-content:center;">
      <i class="ti ti-bell" style="font-size:16px;color:#eef0f3;"></i>
      <span style="position:absolute;top:-2px;right:-2px;width:15px;height:15px;border-radius:50%;background:#e85c4a;color:#fff;font-size:9px;display:flex;align-items:center;justify-content:center;">2</span>
    </button>
    <div style="width:32px;height:32px;border-radius:50%;background:#e8a33d;display:flex;align-items:center;justify-content:center;color:#3a2705;font-size:12px;font-weight:500;">JM</div>
  </div>
</div>"""

BOTTOMNAV = """<div style="display:flex;align-items:center;border-top:0.5px solid #262b33;padding:6px 0;">
  <button style="flex:1;border:none;background:transparent;padding:8px 0;display:flex;flex-direction:column;align-items:center;gap:2px;color:{c0};"><i class="ti ti-home" style="font-size:18px;"></i><span style="font-size:10px;">Início</span></button>
  <button style="flex:1;border:none;background:transparent;padding:8px 0;display:flex;flex-direction:column;align-items:center;gap:2px;color:{c1};"><i class="ti ti-receipt" style="font-size:18px;"></i><span style="font-size:10px;">Atividade</span></button>
  <button style="width:44px;height:44px;border-radius:50%;background:#e8a33d;border:none;display:flex;align-items:center;justify-content:center;margin:0 4px;"><i class="ti ti-plus" style="font-size:20px;color:#2a1c04;"></i></button>
  <button style="flex:1;border:none;background:transparent;padding:8px 0;display:flex;flex-direction:column;align-items:center;gap:2px;color:{c2};"><i class="ti ti-chart-pie" style="font-size:18px;"></i><span style="font-size:10px;">Insights</span></button>
  <button style="flex:1;border:none;background:transparent;padding:8px 0;display:flex;flex-direction:column;align-items:center;gap:2px;color:{c3};"><i class="ti ti-trophy" style="font-size:18px;"></i><span style="font-size:10px;">Metas</span></button>
</div>"""

def navcolors(active):
    cols = {"home":"#8a8f98","activity":"#8a8f98","insights":"#8a8f98","metas":"#8a8f98"}
    cols[active] = "#e8a33d"
    return BOTTOMNAV.format(c0=cols["home"], c1=cols["activity"], c2=cols["insights"], c3=cols["metas"])

SCREEN_HOME = """<div style="padding:0.25rem 1.1rem 1rem;">
  <p style="font-size:11px;color:#8a8f98;letter-spacing:0.04em;margin:0 0 2px;">FLUXO DE CAIXA · AGOSTO</p>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:10px;">
    <span style="font-size:30px;font-weight:500;color:#f5f6f8;">R$ 1.870</span>
    <span style="font-size:11px;background:#1c3327;color:#4fd48c;padding:2px 8px;border-radius:20px;">líquido</span>
  </div>
  <div style="display:flex;gap:10px;margin-bottom:14px;">
    <div style="flex:1;background:#1c2028;border-radius:12px;padding:10px 12px;">
      <p style="font-size:11px;color:#8a8f98;margin:0 0 2px;">Entrou</p>
      <p style="font-size:15px;font-weight:500;margin:0;color:#4fd48c;">R$ 8.000</p>
    </div>
    <div style="flex:1;background:#1c2028;border-radius:12px;padding:10px 12px;">
      <p style="font-size:11px;color:#8a8f98;margin:0 0 2px;">Saiu</p>
      <p style="font-size:15px;font-weight:500;margin:0;color:#f5f6f8;">R$ 6.130</p>
    </div>
  </div>
  <div style="background:#1c2028;border-radius:14px;padding:14px;margin-bottom:12px;display:flex;gap:14px;align-items:center;">
    <div style="width:76px;height:76px;border-radius:50%;flex-shrink:0;background:conic-gradient(#e8a33d 0% 29%, #4fb7d4 29% 54%, #d4658c 54% 80%, #7f8ff0 80% 88%, #565c66 88% 100%);display:flex;align-items:center;justify-content:center;">
      <div style="width:48px;height:48px;border-radius:50%;background:#1c2028;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <span style="font-size:12px;font-weight:500;color:#f5f6f8;">6.130</span>
      </div>
    </div>
    <div style="flex:1;display:flex;flex-direction:column;gap:5px;">
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span><i class="ti ti-point-filled" style="color:#e8a33d;font-size:10px;"></i> Moradia</span><span style="color:#8a8f98;">29%</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span><i class="ti ti-point-filled" style="color:#4fb7d4;font-size:10px;"></i> Alimentação</span><span style="color:#8a8f98;">25%</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span><i class="ti ti-point-filled" style="color:#d4658c;font-size:10px;"></i> Lazer/compras</span><span style="color:#8a8f98;">26%</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span><i class="ti ti-point-filled" style="color:#7f8ff0;font-size:10px;"></i> Transporte</span><span style="color:#8a8f98;">8%</span></div>
    </div>
  </div>
  <div style="display:flex;gap:10px;margin-bottom:14px;">
    <div style="flex:1;background:#1c2028;border-radius:12px;padding:10px 12px;display:flex;align-items:center;gap:10px;">
      <div style="width:34px;height:34px;border-radius:50%;background:#26343a;display:flex;align-items:center;justify-content:center;color:#4fd4c4;font-size:13px;font-weight:500;">78</div>
      <div><p style="font-size:11px;color:#8a8f98;margin:0;">Saúde financeira</p><p style="font-size:12px;color:#e8a33d;margin:0;">Atenção</p></div>
    </div>
    <div style="flex:1;background:#1c2028;border-radius:12px;padding:10px 12px;">
      <p style="font-size:11px;color:#8a8f98;margin:0 0 2px;"><i class="ti ti-trending-up" style="font-size:12px;color:#4fd48c;"></i> Investido no mês</p>
      <p style="font-size:15px;font-weight:500;margin:0;color:#4fd48c;">R$ 1.200</p>
    </div>
  </div>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">REGRA 50-30-20</p>
  <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:12px;">
    <div>
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span style="color:#cfd3d9;">Necessidades</span><span style="color:#8a8f98;">R$ 3.800/4.000</span></div>
      <div style="height:5px;background:#262b33;border-radius:4px;overflow:hidden;"><div style="height:100%;width:95%;background:#4fb7d4;"></div></div>
    </div>
    <div>
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span style="color:#cfd3d9;">Desejos</span><span style="color:#e8a33d;">R$ 2.330/2.400</span></div>
      <div style="height:5px;background:#262b33;border-radius:4px;overflow:hidden;"><div style="height:100%;width:97%;background:#e8a33d;"></div></div>
    </div>
    <div>
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span style="color:#cfd3d9;">Poupança/metas</span><span style="color:#8a8f98;">R$ 1.200/1.600</span></div>
      <div style="height:5px;background:#262b33;border-radius:4px;overflow:hidden;"><div style="height:100%;width:75%;background:#4fd48c;"></div></div>
    </div>
  </div>
  <div style="background:#1c2b24;border-radius:12px;padding:12px 14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <span style="font-size:12px;color:#4fd48c;"><i class="ti ti-shield-check" style="font-size:13px;"></i> Reserva de emergência</span>
      <span style="font-size:11px;color:#4fd48c;">42%</span>
    </div>
    <div style="height:5px;background:#26342c;border-radius:4px;overflow:hidden;"><div style="height:100%;width:42%;background:#4fd48c;"></div></div>
  </div>
</div>"""

SCREEN_ACTIVITY = """<div style="padding:0.25rem 1.1rem 1rem;">
  <p style="font-size:11px;color:#8a8f98;letter-spacing:0.04em;margin:0 0 10px;">HOJE</p>
  <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:16px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;border-radius:50%;background:#26343a;display:flex;align-items:center;justify-content:center;"><i class="ti ti-coffee" style="font-size:16px;color:#4fb7d4;"></i></div>
      <div style="flex:1;"><p style="font-size:13px;margin:0;color:#f5f6f8;">Cafeteria</p><p style="font-size:11px;color:#8a8f98;margin:0;">Alimentação</p></div>
      <span style="font-size:13px;color:#f5f6f8;">-R$ 18</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;border-radius:50%;background:#332a1c;display:flex;align-items:center;justify-content:center;"><i class="ti ti-bus" style="font-size:16px;color:#e8a33d;"></i></div>
      <div style="flex:1;"><p style="font-size:13px;margin:0;color:#f5f6f8;">Transporte app</p><p style="font-size:11px;color:#8a8f98;margin:0;">Transporte</p></div>
      <span style="font-size:13px;color:#f5f6f8;">-R$ 35</span>
    </div>
  </div>
  <p style="font-size:11px;color:#8a8f98;letter-spacing:0.04em;margin:0 0 10px;">ONTEM</p>
  <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:16px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;border-radius:50%;background:#2a2333;display:flex;align-items:center;justify-content:center;"><i class="ti ti-shopping-bag" style="font-size:16px;color:#d4658c;"></i></div>
      <div style="flex:1;"><p style="font-size:13px;margin:0;color:#f5f6f8;">Loja de roupas</p><p style="font-size:11px;color:#8a8f98;margin:0;">Compras</p></div>
      <span style="font-size:13px;color:#f5f6f8;">-R$ 210</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;border-radius:50%;background:#1c3327;display:flex;align-items:center;justify-content:center;"><i class="ti ti-trending-up" style="font-size:16px;color:#4fd48c;"></i></div>
      <div style="flex:1;"><p style="font-size:13px;margin:0;color:#f5f6f8;">Aporte Tesouro Selic</p><p style="font-size:11px;color:#8a8f98;margin:0;">Investimentos</p></div>
      <span style="font-size:13px;color:#4fd48c;">+R$ 400</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;border-radius:50%;background:#332a1c;display:flex;align-items:center;justify-content:center;"><i class="ti ti-home" style="font-size:16px;color:#e8a33d;"></i></div>
      <div style="flex:1;"><p style="font-size:13px;margin:0;color:#f5f6f8;">Aluguel</p><p style="font-size:11px;color:#8a8f98;margin:0;">Moradia</p></div>
      <span style="font-size:13px;color:#f5f6f8;">-R$ 1.800</span>
    </div>
  </div>
</div>"""

SCREEN_INSIGHTS = """<div style="padding:0.25rem 1.1rem 1rem;">
  <div style="background:#1c2b24;border-radius:12px;padding:12px 14px;margin-bottom:12px;">
    <p style="font-size:12px;color:#4fd48c;margin:0 0 4px;font-weight:500;"><i class="ti ti-chart-line" style="font-size:13px;"></i> Projeção de fechamento</p>
    <p style="font-size:12px;color:#9dc9ac;margin:0;">No ritmo atual, você deve fechar o mês gastando <span style="color:#f5f6f8;font-weight:500;">R$ 6.450</span> (81% da renda). Atualiza a cada novo gasto e todo dia à meia-noite.</p>
  </div>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">MÊS A MÊS POR CATEGORIA</p>
  <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">Lazer</span><span style="font-size:12px;color:#e85c4a;">+18%</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">Mercado</span><span style="font-size:12px;color:#e8a33d;">+6%</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">Compras</span><span style="font-size:12px;color:#4fd48c;">-5%</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">Transporte</span><span style="font-size:12px;color:#8a8f98;">0%</span></div>
  </div>
  <div style="display:flex;gap:10px;margin-bottom:14px;">
    <div style="flex:1;background:#332618;border-radius:12px;padding:10px 12px;">
      <p style="font-size:11px;color:#f5c98a;margin:0 0 2px;">Em alta</p>
      <p style="font-size:13px;color:#f5f6f8;margin:0;">Lazer · +18%</p>
    </div>
    <div style="flex:1;background:#1c3327;border-radius:12px;padding:10px 12px;">
      <p style="font-size:11px;color:#8fe4b3;margin:0 0 2px;">Em queda</p>
      <p style="font-size:13px;color:#f5f6f8;margin:0;">Compras · -5%</p>
    </div>
  </div>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">ASSINATURAS RECORRENTES</p>
  <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:6px;">
    <div style="display:flex;align-items:center;gap:10px;"><div style="width:30px;height:30px;border-radius:50%;background:#26343a;display:flex;align-items:center;justify-content:center;"><i class="ti ti-device-tv" style="font-size:14px;color:#4fb7d4;"></i></div><span style="flex:1;font-size:12px;color:#cfd3d9;">Streaming</span><span style="font-size:12px;color:#8a8f98;">R$ 80/mês</span></div>
    <div style="display:flex;align-items:center;gap:10px;"><div style="width:30px;height:30px;border-radius:50%;background:#2a2333;display:flex;align-items:center;justify-content:center;"><i class="ti ti-barbell" style="font-size:14px;color:#d4658c;"></i></div><span style="flex:1;font-size:12px;color:#cfd3d9;">Academia</span><span style="font-size:12px;color:#8a8f98;">R$ 120/mês</span></div>
  </div>
  <p style="font-size:11px;color:#8a8f98;margin:6px 0 14px;">Total recorrente detectado: <span style="color:#f5f6f8;">R$ 200/mês</span></p>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">TOP 5 MAIORES GASTOS</p>
  <div style="display:flex;flex-direction:column;gap:7px;margin-bottom:14px;">
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">1. Aluguel</span><span style="font-size:12px;color:#f5f6f8;">R$ 1.800</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">2. Loja de roupas</span><span style="font-size:12px;color:#f5f6f8;">R$ 210</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">3. Mercado semanal</span><span style="font-size:12px;color:#f5f6f8;">R$ 190</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">4. Show/ingresso</span><span style="font-size:12px;color:#f5f6f8;">R$ 180</span></div>
    <div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:#cfd3d9;">5. Transporte app</span><span style="font-size:12px;color:#f5f6f8;">R$ 35</span></div>
  </div>
  <div style="background:#241c33;border-radius:12px;padding:12px 14px;">
    <p style="font-size:12px;color:#c3b3f0;margin:0 0 4px;font-weight:500;"><i class="ti ti-bulb" style="font-size:13px;"></i> Sugestão prática</p>
    <p style="font-size:12px;color:#b3a6d1;margin:0;">Se cortar R$ 150 em delivery esse mês, você bate a meta de poupança de 20%.</p>
  </div>
</div>"""

SCREEN_METAS = """<div style="padding:0.25rem 1.1rem 1rem;">
  <div style="background:#1c2028;border-radius:14px;padding:14px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="font-weight:500;font-size:14px;">Nível 4 · Economista em treino</span>
      <span style="font-size:12px;color:#8a8f98;">320/500 XP</span>
    </div>
    <div style="height:6px;background:#262b33;border-radius:4px;overflow:hidden;margin-bottom:10px;"><div style="height:100%;width:64%;background:#7f8ff0;"></div></div>
    <div style="display:flex;flex-direction:column;gap:5px;">
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span style="color:#8a8f98;">Registro de gastos</span><span style="color:#cfd3d9;">+80 XP</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span style="color:#8a8f98;">Semanas dentro do teto</span><span style="color:#cfd3d9;">+90 XP</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span style="color:#8a8f98;">Avanço na reserva</span><span style="color:#cfd3d9;">+80 XP</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;"><span style="color:#8a8f98;">Cofrinho ativo</span><span style="color:#cfd3d9;">+5 XP</span></div>
    </div>
  </div>
  <div style="background:#1c2028;border-radius:14px;padding:12px 14px;margin-bottom:12px;display:flex;align-items:center;gap:10px;">
    <i class="ti ti-calendar-check" style="font-size:18px;color:#4fb7d4;"></i>
    <div>
      <p style="font-size:13px;margin:0;color:#f5f6f8;">12 dias ativos este mês</p>
      <p style="font-size:11px;color:#8a8f98;margin:2px 0 0;">Sem pressão de sequência — cada dia que você registra conta pro seu total.</p>
    </div>
  </div>
  <div style="background:#241c33;border-radius:14px;padding:14px;margin-bottom:14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <span style="font-size:13px;color:#c3b3f0;font-weight:500;"><i class="ti ti-pig-money" style="font-size:15px;"></i> Cofrinho de arredondamento</span>
      <span style="font-size:11px;background:#3a2f52;color:#c3b3f0;padding:2px 8px;border-radius:20px;">ativo</span>
    </div>
    <p style="font-size:22px;font-weight:500;color:#f5f6f8;margin:0 0 4px;">R$ 47</p>
    <p style="font-size:12px;color:#b3a6d1;margin:0 0 10px;">Cada compra arredonda pro R$ mais próximo e guarda a diferença. Ainda não move dinheiro sozinho — você confirma quando quiser.</p>
    <button style="width:100%;background:#2f2540;color:#e8dfff;border:none;border-radius:8px;padding:8px 0;font-size:12px;">Transferir pra reserva agora</button>
  </div>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">METAS DO MÊS</p>
  <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">
    <div style="display:flex;align-items:center;gap:10px;"><i class="ti ti-check" style="font-size:16px;color:#4fd48c;"></i><span style="font-size:13px;color:#cfd3d9;">Ficar dentro do teto de necessidades</span></div>
    <div style="display:flex;align-items:center;gap:10px;"><i class="ti ti-clock" style="font-size:16px;color:#e8a33d;"></i><span style="font-size:13px;color:#cfd3d9;">Bater 20% de poupança (faltam R$ 400)</span></div>
    <div style="display:flex;align-items:center;gap:10px;"><i class="ti ti-shield-check" style="font-size:16px;color:#8a8f98;"></i><span style="font-size:13px;color:#cfd3d9;">Reserva de emergência: 42% do alvo</span></div>
  </div>
  <p style="font-size:11px;font-weight:500;color:#8a8f98;letter-spacing:0.04em;margin:0 0 8px;">CONQUISTAS</p>
  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;">
    <div style="background:#1c3327;border-radius:12px;padding:10px;text-align:center;"><i class="ti ti-trophy" style="font-size:18px;color:#4fd48c;"></i><p style="font-size:11px;margin:4px 0 0;color:#4fd48c;">Mês nas metas</p></div>
    <div style="background:#241c33;border-radius:12px;padding:10px;text-align:center;"><i class="ti ti-pig-money" style="font-size:18px;color:#c3b3f0;"></i><p style="font-size:11px;margin:4px 0 0;color:#c3b3f0;">Primeiro cofrinho</p></div>
    <div style="background:#1c2028;border-radius:12px;padding:10px;text-align:center;opacity:0.6;"><i class="ti ti-lock" style="font-size:18px;color:#8a8f98;"></i><p style="font-size:11px;margin:4px 0 0;color:#8a8f98;">7 dias sem delivery</p></div>
    <div style="background:#1c2028;border-radius:12px;padding:10px;text-align:center;opacity:0.6;"><i class="ti ti-lock" style="font-size:18px;color:#8a8f98;"></i><p style="font-size:11px;margin:4px 0 0;color:#8a8f98;">20 dias ativos no mês</p></div>
  </div>
</div>"""

SCREEN_NOTIFICACOES = """<div style="padding:0.25rem 1.1rem 1rem;">
  <p style="font-size:13px;font-weight:500;color:#f5f6f8;margin:0 0 12px;">Notificações</p>
  <div style="display:flex;flex-direction:column;gap:10px;">
    <div style="background:#332618;border-left:3px solid #e8a33d;border-radius:8px;padding:10px 12px;">
      <p style="font-size:12px;color:#f5c98a;margin:0;font-weight:500;">Desejos em 95% do teto</p>
      <p style="font-size:12px;color:#c9b494;margin:4px 0 0;">Você já usou 95% do limite de desejos este mês.</p>
    </div>
    <div style="background:#331c1c;border-left:3px solid #e85c4a;border-radius:8px;padding:10px 12px;">
      <p style="font-size:12px;color:#f3a196;margin:0;font-weight:500;">Ritmo atual pode fechar negativo</p>
      <p style="font-size:12px;color:#cf9c95;margin:4px 0 0;">Projeção linear do gasto diário passou de 97% da renda — inclui os gastos lançados por foto.</p>
    </div>
    <div style="background:#1c3327;border-left:3px solid #4fd48c;border-radius:8px;padding:10px 12px;">
      <p style="font-size:12px;color:#8fe4b3;margin:0;font-weight:500;">Necessidades dentro do teto</p>
      <p style="font-size:12px;color:#9dc9ac;margin:4px 0 0;">Você está usando 95% do limite de 50% para necessidades.</p>
    </div>
    <div style="background:#1c2028;border-left:3px solid #7f8ff0;border-radius:8px;padding:10px 12px;">
      <p style="font-size:12px;color:#c3c9f5;margin:0;font-weight:500;">Reserva chegou a 42%</p>
      <p style="font-size:12px;color:#9ea3c9;margin:4px 0 0;">Faltam R$ 13.300 pra bater o alvo da reserva de emergência.</p>
    </div>
  </div>
</div>"""

SCREEN_ADICIONAR = """<div style="padding:0.25rem 1.1rem 1rem;">
  <div style="display:flex;background:#1c2028;border-radius:20px;padding:3px;margin-bottom:16px;">
    <button style="flex:1;background:#f5f6f8;color:#14171c;border:none;border-radius:18px;padding:8px 0;font-size:12px;">Despesa</button>
    <button style="flex:1;background:transparent;color:#8a8f98;border:none;border-radius:18px;padding:8px 0;font-size:12px;">Receita</button>
    <button style="flex:1;background:transparent;color:#8a8f98;border:none;border-radius:18px;padding:8px 0;font-size:12px;">Transferência</button>
  </div>
  <p style="text-align:center;font-size:30px;font-weight:500;color:#f5f6f8;margin:0 0 6px;">R$ 0</p>
  <p style="text-align:center;font-size:12px;color:#8a8f98;margin:0 0 16px;">Toque no teclado, escaneie ou dite o gasto</p>
  <div style="display:flex;gap:10px;margin-bottom:16px;">
    <button style="flex:1;background:#1c2028;color:#eef0f3;border:none;border-radius:10px;padding:10px 0;font-size:12px;"><i class="ti ti-camera" style="font-size:14px;"></i> Escanear recibo</button>
    <button style="flex:1;background:#1c2028;color:#eef0f3;border:none;border-radius:10px;padding:10px 0;font-size:12px;"><i class="ti ti-microphone" style="font-size:14px;"></i> Ditar por voz</button>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">
    <span style="background:#1c2028;color:#cfd3d9;font-size:11px;padding:6px 12px;border-radius:20px;">Moradia</span>
    <span style="background:#1c2028;color:#cfd3d9;font-size:11px;padding:6px 12px;border-radius:20px;">Mercado</span>
    <span style="background:#1c2028;color:#cfd3d9;font-size:11px;padding:6px 12px;border-radius:20px;">Transporte</span>
    <span style="background:#1c2028;color:#cfd3d9;font-size:11px;padding:6px 12px;border-radius:20px;">Lazer</span>
    <span style="background:#1c2028;color:#cfd3d9;font-size:11px;padding:6px 12px;border-radius:20px;">Compras</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;">
    """ + "".join(f'<button style="background:#1c2028;color:#eef0f3;border:none;border-radius:10px;padding:12px 0;font-size:15px;">{n}</button>' for n in range(1,10)) + """
  </div>
</div>"""

def onboarding_screen(icon, iconbg, iconcolor, title, body, dot_index, cta_label):
    dots = ""
    for i in range(3):
        active = i == dot_index
        w = "18px" if active else "6px"
        bg = "#e8a33d" if active else "#262b33"
        dots += f'<span style="width:{w};height:4px;border-radius:4px;background:{bg};"></span>'
    return f"""<div style="padding:2rem 1.4rem 1.5rem;min-height:520px;display:flex;flex-direction:column;">
  <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;">
    <div style="width:64px;height:64px;border-radius:50%;background:{iconbg};display:flex;align-items:center;justify-content:center;margin-bottom:20px;"><i class="ti {icon}" style="font-size:28px;color:{iconcolor};"></i></div>
    <p style="font-size:20px;font-weight:500;color:#f5f6f8;margin:0 0 10px;">{title}</p>
    <p style="font-size:13px;color:#8a8f98;margin:0;line-height:1.6;">{body}</p>
  </div>
  <div style="display:flex;justify-content:center;gap:6px;margin-bottom:16px;">{dots}</div>
  <button style="width:100%;background:#e8a33d;color:#2a1c04;border:none;border-radius:10px;padding:12px 0;font-size:14px;font-weight:500;">{cta_label}</button>
</div>"""

SCREEN_CADASTRO = """<div style="padding:1.6rem 1.4rem 1.5rem;min-height:520px;">
  <p style="font-size:18px;font-weight:500;color:#f5f6f8;margin:0 0 4px;">Crie sua conta grátis</p>
  <p style="font-size:12px;color:#8a8f98;margin:0 0 20px;">Leva menos de um minuto. Sem cartão, sem compromisso.</p>
  <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px;">
    <button style="width:100%;background:#1c2028;color:#eef0f3;border:none;border-radius:10px;padding:11px 0;font-size:13px;display:flex;align-items:center;justify-content:center;gap:8px;"><i class="ti ti-brand-google" style="font-size:16px;"></i> Continuar com Google</button>
    <button style="width:100%;background:#1c2028;color:#eef0f3;border:none;border-radius:10px;padding:11px 0;font-size:13px;display:flex;align-items:center;justify-content:center;gap:8px;"><i class="ti ti-brand-apple" style="font-size:16px;"></i> Continuar com Apple</button>
  </div>
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
    <div style="flex:1;height:1px;background:#262b33;"></div>
    <span style="font-size:11px;color:#8a8f98;">ou com e-mail</span>
    <div style="flex:1;height:1px;background:#262b33;"></div>
  </div>
  <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px;">
    <input type="text" placeholder="Seu nome" style="width:100%;background:#1c2028;border:1px solid #262b33;border-radius:10px;padding:11px 12px;color:#eef0f3;font-size:13px;">
    <input type="email" placeholder="nome@email.com" style="width:100%;background:#1c2028;border:1px solid #262b33;border-radius:10px;padding:11px 12px;color:#eef0f3;font-size:13px;">
    <input type="password" placeholder="Crie uma senha" style="width:100%;background:#1c2028;border:1px solid #262b33;border-radius:10px;padding:11px 12px;color:#eef0f3;font-size:13px;">
  </div>
  <label style="display:flex;align-items:flex-start;gap:8px;margin-bottom:18px;">
    <input type="checkbox" style="margin-top:2px;">
    <span style="font-size:11px;color:#8a8f98;line-height:1.5;">Aceito os termos de uso e a política de privacidade, e autorizo o processamento dos meus dados financeiros pra gerar os insights do app.</span>
  </label>
  <button style="width:100%;background:#e8a33d;color:#2a1c04;border:none;border-radius:10px;padding:12px 0;font-size:14px;font-weight:500;margin-bottom:10px;">Criar minha conta</button>
  <button style="width:100%;background:transparent;color:#8a8f98;border:none;padding:6px 0;font-size:12px;">Já tenho conta · Entrar</button>
</div>"""

pages = [
    ("01-onboarding-1", "Onboarding 1", onboarding_screen("ti-chart-pie", "#1c2b24", "#4fd48c",
        "Veja pra onde seu dinheiro vai",
        "Conecte sua conta, importe o extrato ou fotografe o recibo — o app categoriza tudo sozinho, sem planilha.",
        0, "Continuar")),
    ("02-onboarding-2", "Onboarding 2", onboarding_screen("ti-trophy", "#241c33", "#c3b3f0",
        "Bata suas metas com a regra 50-30-20",
        "Necessidades, desejos e poupança sempre visíveis, com XP, níveis e um cofrinho que guarda o troco de cada compra.",
        1, "Continuar")),
    ("03-onboarding-3", "Onboarding 3", onboarding_screen("ti-shield-check", "#332618", "#e8a33d",
        "Durma tranquilo com sua reserva",
        "O app calcula sua reserva de emergência ideal e avisa antes do mês fechar no vermelho — não depois.",
        2, "Criar minha conta")),
    ("04-cadastro", "Cadastro", SCREEN_CADASTRO),
    ("05-inicio", "Início", TOPBAR + SCREEN_HOME + navcolors("home")),
    ("06-atividade", "Atividade", TOPBAR + SCREEN_ACTIVITY + navcolors("activity")),
    ("07-insights", "Insights", TOPBAR + SCREEN_INSIGHTS + navcolors("insights")),
    ("08-metas", "Metas", TOPBAR + SCREEN_METAS + navcolors("metas")),
    ("09-notificacoes", "Notificações", TOPBAR + SCREEN_NOTIFICACOES + navcolors("home")),
    ("10-adicionar", "Adicionar", TOPBAR + SCREEN_ADICIONAR),
]

for filename, title, body in pages:
    html = HEAD.replace("{title}", title) + body + FOOT
    with open(os.path.join(OUT_DIR, f"{filename}.html"), "w", encoding="utf-8") as f:
        f.write(html)

print("Gerados:", len(pages), "arquivos em", OUT_DIR)
