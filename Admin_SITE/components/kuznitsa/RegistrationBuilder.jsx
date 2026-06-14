import React, { useState } from 'react';
import { Settings, Save, Plus, X, GripVertical, FileText, CheckSquare, Image as ImageIcon, AlignLeft, Eye, LayoutTemplate, Wrench } from 'lucide-react';

export default function RegistrationBuilder() {
  const [blocks, setBlocks] = useState([
    { id: '1', type: 'text', label: 'Как вас зовут?', required: true },
    { id: '2', type: 'photo', label: 'Прикрепите ваше фото', required: false }
  ]);
  const [selectedBlockId, setSelectedBlockId] = useState(null);

  const blockTypes = [
    { type: 'text', name: 'Текстовый ответ', icon: AlignLeft },
    { type: 'photo', name: 'Фотография', icon: ImageIcon },
    { type: 'checkbox', name: 'Согласие (Галочка)', icon: CheckSquare },
    { type: 'select', name: 'Выбор из списка', icon: FileText }
  ];

  const addBlock = (type) => {
    const newBlock = { id: Date.now().toString(), type, label: 'Новый вопрос', required: false };
    setBlocks([...blocks, newBlock]);
    setSelectedBlockId(newBlock.id);
  };

  const removeBlock = (id, e) => {
    e.stopPropagation();
    setBlocks(blocks.filter(b => b.id !== id));
    if (selectedBlockId === id) setSelectedBlockId(null);
  };

  const selectedBlock = blocks.find(b => b.id === selectedBlockId);

  const updateSelectedBlock = (changes) => {
    setBlocks(blocks.map(b => b.id === selectedBlockId ? { ...b, ...changes } : b));
  };

  return (
    <div className="h-full flex flex-col bg-sff">
      {/* Шапка */}
      <div className="flex-none px-6 py-4 border-b border-bd flex justify-between items-center bg-white relative overflow-hidden">
        {/* Декоративная лента для шапки */}
        <div className="absolute top-0 left-0 w-full h-1 bg-repeating-linear-gradient-kuznitsa opacity-30" />
        <style>{`
          .bg-repeating-linear-gradient-kuznitsa {
            background: repeating-linear-gradient(45deg, #FFC800 0 12px, #000 12px 24px);
          }
        `}</style>
        
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-xl bg-[color-mix(in_oklab,var(--warn)_15%,transparent)] text-warn flex items-center justify-center">
            <Wrench size={20} />
          </div>
          <div>
            <h1 className="text-xl font-black text-tx leading-tight">Регистрация-конструктор <span className="text-[10px] bg-warn text-white px-2 py-0.5 rounded-full uppercase ml-2 tracking-wider align-middle">Альфа</span></h1>
            <p className="text-sm text-lbl font-medium">Соберите свою анкету регистрации</p>
          </div>
        </div>
        <div className="flex gap-2 relative z-10">
          <button className="px-4 py-2 rounded-xl bg-sf2 hover:bg-bd transition-colors text-tx font-bold text-sm flex items-center gap-2">
            <LayoutTemplate size={16} /> Шаблоны
          </button>
          <button className="px-4 py-2 rounded-xl bg-sf2 hover:bg-bd transition-colors text-tx font-bold text-sm flex items-center gap-2">
            <Eye size={16} /> Предпросмотр
          </button>
          <button className="pulse-btn-glow px-4 py-2 rounded-xl bg-cta hover:bg-blue-600 text-white font-bold text-sm flex items-center gap-2 shadow-lg shadow-blue-500/20">
            <Save size={16} /> Сохранить
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Левая панель: Инструменты */}
        <div className="w-64 border-r border-bd bg-white flex flex-col p-4 overflow-y-auto">
          <h3 className="text-xs font-bold text-lbl uppercase tracking-wider mb-4">Блоки анкеты</h3>
          <div className="space-y-2">
            {blockTypes.map(bt => {
              const Icon = bt.icon;
              return (
                <button
                  key={bt.type}
                  onClick={() => addBlock(bt.type)}
                  className="w-full flex items-center gap-3 p-3 rounded-xl border border-bd hover:border-cta hover:shadow-md transition-all text-left bg-sff group"
                >
                  <div className="text-txd group-hover:text-cta"><Icon size={18} /></div>
                  <span className="text-sm font-bold text-tx">{bt.name}</span>
                </button>
              );
            })}
          </div>
          
          <h3 className="text-xs font-bold text-lbl uppercase tracking-wider mt-8 mb-4">Настройки процесса</h3>
          <button className="w-full text-left p-3 rounded-xl bg-sf2 hover:bg-bd transition-colors mb-2">
            <div className="text-sm font-bold text-tx">Приветствие</div>
            <div className="text-xs text-lbl mt-0.5 truncate">Первое сообщение бота...</div>
          </button>
          <button className="w-full text-left p-3 rounded-xl bg-sf2 hover:bg-bd transition-colors">
            <div className="text-sm font-bold text-tx">Завершение</div>
            <div className="text-xs text-lbl mt-0.5 truncate">Сообщение об успехе...</div>
          </button>
        </div>

        {/* Центр: Канвас */}
        <div className="flex-1 bg-sf2 p-8 overflow-y-auto">
          <div className="max-w-2xl mx-auto space-y-3">
            {blocks.length === 0 ? (
              <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-bd">
                <p className="text-txd font-medium">Анкета пуста. Добавьте блоки из панели слева.</p>
              </div>
            ) : (
              blocks.map((block, i) => (
                <div
                  key={block.id}
                  onClick={() => setSelectedBlockId(block.id)}
                  className={`group relative bg-white p-5 rounded-2xl border-2 transition-all cursor-pointer ${
                    selectedBlockId === block.id ? 'border-cta shadow-md' : 'border-transparent hover:border-bd shadow-sm'
                  }`}
                >
                  <div className="absolute left-2 top-1/2 -translate-y-1/2 text-lbl opacity-0 group-hover:opacity-100 cursor-grab">
                    <GripVertical size={20} />
                  </div>
                  <button
                    onClick={(e) => removeBlock(block.id, e)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-xl text-lbl hover:bg-red-50 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <X size={16} />
                  </button>
                  
                  <div className="pl-6 pr-10">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-black text-white bg-txd px-2 py-0.5 rounded-md">ШАГ {i + 1}</span>
                      <span className="text-[10px] font-bold text-lbl uppercase">{blockTypes.find(t => t.type === block.type)?.name}</span>
                      {block.required && <span className="text-[10px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-md">* Обязательно</span>}
                    </div>
                    <div className="text-lg font-black text-tx mt-2">{block.label || 'Без текста'}</div>
                    {block.type === 'select' && (
                      <div className="mt-3 flex gap-2 flex-wrap">
                        {['Вариант 1', 'Вариант 2'].map((opt, idx) => (
                          <div key={idx} className="px-3 py-1 bg-sf2 border border-bd rounded-lg text-sm text-txd font-medium">{opt}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Правая панель: Настройки свойства */}
        <div className="w-80 border-l border-bd bg-white flex flex-col overflow-y-auto">
          {selectedBlock ? (
            <div className="p-5">
              <h3 className="text-sm font-black text-tx mb-4 border-b border-bd pb-4">Свойства блока</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-lbl uppercase tracking-wider mb-2">Текст вопроса</label>
                  <textarea
                    value={selectedBlock.label}
                    onChange={e => updateSelectedBlock({ label: e.target.value })}
                    className="w-full bg-sf2 border border-bd rounded-xl p-3 text-sm text-tx focus:outline-none focus:border-cta font-medium resize-none h-24"
                    placeholder="Например: Как вас зовут?"
                  />
                </div>
                
                <label className="flex items-center gap-3 p-3 border border-bd rounded-xl cursor-pointer hover:bg-sf2 transition-colors">
                  <input
                    type="checkbox"
                    checked={selectedBlock.required}
                    onChange={e => updateSelectedBlock({ required: e.target.checked })}
                    className="w-4 h-4 rounded text-cta focus:ring-cta border-bd"
                  />
                  <span className="text-sm font-bold text-tx">Обязательный вопрос</span>
                </label>
                
                {selectedBlock.type === 'select' && (
                  <div className="pt-4 border-t border-bd">
                    <label className="block text-xs font-bold text-lbl uppercase tracking-wider mb-2">Варианты ответа</label>
                    <div className="space-y-2 mb-3">
                      <div className="flex gap-2">
                        <input className="flex-1 bg-sf2 border border-bd rounded-xl px-3 py-2 text-sm text-tx" defaultValue="Вариант 1" />
                        <button className="p-2 text-lbl hover:text-danger rounded-lg"><X size={16}/></button>
                      </div>
                      <div className="flex gap-2">
                        <input className="flex-1 bg-sf2 border border-bd rounded-xl px-3 py-2 text-sm text-tx" defaultValue="Вариант 2" />
                        <button className="p-2 text-lbl hover:text-danger rounded-lg"><X size={16}/></button>
                      </div>
                    </div>
                    <button className="w-full py-2 border border-dashed border-cta text-cta font-bold text-sm rounded-xl hover:bg-[color-mix(in_oklab,var(--cta)_5%,transparent)] transition-colors flex items-center justify-center gap-2">
                      <Plus size={16} /> Добавить вариант
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
              <Settings size={32} className="text-bd mb-3" />
              <p className="text-sm font-medium text-lbl">Выберите блок на холсте для редактирования его свойств</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
